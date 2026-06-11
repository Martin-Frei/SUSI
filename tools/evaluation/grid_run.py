"""
SUSI Evaluation — Grid Run
===========================
Haupt-Script: lädt Config + Gold-Set, iteriert alle Parameter-Kombinationen
und schreibt die Ergebnisse in eine CSV-Datei.

Voraussetzung: indexer.py wurde bereits ausgeführt (Collections existieren).

Jeder Lauf bekommt eine eigene CSV mit Timestamp im Namen:
    tools/evaluation/results/eval_20260524_1423_smoke.csv

C:/Users/tsinn/VSCode/Repos/SUSI/susi_env/Scripts/Activate.ps1 


Aufruf:
    # Smoke-Test (4 Fragen)
    python tools/evaluation/grid_run.py --mode smoke

    # Mit manueller Bewertung
    python tools/evaluation/grid_run.py --mode smoke --manual

    # Voller Grid-Lauf (40 Fragen)
    python tools/evaluation/grid_run.py --mode full --manual

    # Nur bestimmtes LLM + Embedding testen (Debug)
    python tools/evaluation/grid_run.py --mode smoke --llm qwen2.5-coder:7b --embedding nomic-embed-text

    # Kombinationen zählen ohne auszuführen
    python tools/evaluation/grid_run.py --dry-run

    # Zusammenfassung einer bestehenden CSV
    python tools/evaluation/grid_run.py --summary --csv tools/evaluation/results/eval_xxx.csv

Optionen:
    --mode smoke|full       Fragen-Set (Standard: smoke)
    --config PATH           Pfad zur config.yaml
    --manual                Manuelle Bewertung aktivieren
    --judge                 Judge-Modell aktivieren (braucht ANTHROPIC_API_KEY)
    --llm MODEL             Nur dieses LLM testen
    --embedding MODEL       Nur dieses Embedding-Modell testen
    --summary               Zusammenfassung anzeigen
    --csv PATH              CSV für --summary angeben
    --dry-run               Kombinationen zählen ohne auszuführen
"""

import os
import sys
import yaml
import json
import time
import uuid
import argparse
import itertools
from pathlib import Path
from datetime import datetime
from typing import Optional

# Eigene Module
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from evaluator import (
    EvalResult, CSVWriter,
    score_manuell, score_mit_judge, drucke_zusammenfassung,
    berechne_bert_scores, berechne_rouge_scores, pruefe_ausweichantwort
)
from indexer import get_collection_name, find_config, load_config
from auto_scorer import berechne_auto_score, zeige_auto_score
from eval_meta import schreibe_meta

PROJECT_ROOT = SCRIPT_DIR.parent.parent


# ── Fragen laden ──────────────────────────────────────────────────

def lade_fragen(fragen_path: str, mode: str) -> list:
    """
    Gold-Set laden — smoke (4 Fragen) oder full (40 Fragen).

    Args:
        fragen_path: Pfad zur testfragen.json
        mode:        "smoke" oder "full"

    Returns:
        Liste von Frage-Dicts mit id, frage, referenzantwort, kategorie
    """
    path = Path(fragen_path)
    if not path.exists():
        path = PROJECT_ROOT / fragen_path

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    fragen = []
    if mode == "smoke":
        for f in data["smoke_test"]["fragen"]:
            fragen.append(f)
    else:
        for kategorie, kat_data in data["full_evaluation"]["kategorien"].items():
            for f in kat_data["fragen"]:
                f["kategorie"] = kategorie
                fragen.append(f)

    return fragen


# ── Kombinationen ─────────────────────────────────────────────────

def get_all_combinations(config: dict,
                          filter_llm: str = None,
                          filter_embedding: str = None) -> list:
    """
    Alle aktiven Parameter-Kombinationen aus der config.yaml berechnen.

    Args:
        config:           Geladene config.yaml als Dict
        filter_llm:       Nur dieses LLM verwenden (Debug)
        filter_embedding: Nur dieses Embedding-Modell verwenden (Debug)

    Returns:
        Liste aller Kombinationen als Tupel
    """
    de = config["data_engineering"]
    ret = config["retrieval"]
    gen = config["generation"]

    embeddings = [m for m in de["embedding_models"] if m.get("active", False)]
    if filter_embedding:
        embeddings = [m for m in embeddings if m["name"] == filter_embedding]

    chunk_sizes = de["chunk_sizes"]
    overlaps = de["chunk_overlaps"]
    separators = list(de["separators"].items())
    top_k_values = ret["top_k_values"]
    algorithms = [a for a in ret["algorithms"] if a.get("active", False)]
    score_thresholds = ret["score_thresholds"]

    llms = [m for m in gen["llm_models"] if m.get("active", False)]
    if filter_llm:
        llms = [m for m in llms if m["name"] == filter_llm]

    temperatures = gen["temperatures"]
    prompts = [p for p in gen["system_prompts"] if p.get("active", False)]

    return list(itertools.product(
        embeddings, chunk_sizes, overlaps, separators,
        top_k_values, algorithms, score_thresholds,
        llms, temperatures, prompts
    ))


# ── Output-Pfad mit Timestamp ─────────────────────────────────────

def build_output_path(config: dict, mode: str) -> str:
    """
    Baut den CSV-Ausgabepfad mit Timestamp und Mode.

    Format: tools/evaluation/results/eval_YYYYMMDD_HHMM_smoke.csv

    Jeder Lauf bekommt eine eigene Datei — keine Vermischung von Ergebnissen
    aus verschiedenen Configs oder Zeitpunkten.

    Args:
        config: Geladene config.yaml
        mode:   "smoke" oder "full"

    Returns:
        Vollständiger Pfad zur CSV-Datei
    """
    base = PROJECT_ROOT / "tools" / "evaluation" / "results"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"eval_{timestamp}_{mode}.csv"
    return str(base / filename)


# ── RAG-Anfrage ───────────────────────────────────────────────────

def rag_query(question: str, collection_name: str,
              embedding_model: str, top_k: int,
              algorithm: str, score_threshold: Optional[float],
              llm_model: str, temperature: float,
              system_prompt: str) -> tuple:
    """
    Eine RAG-Anfrage ausführen: Retrieval + Generation.

    Gibt alle relevanten Daten zurück damit BERTScore und ROUGE-L
    Antwort und Chunks einzeln bewerten können.

    Args:
        question:           Die Frage an SUSI
        collection_name:    Name der ChromaDB Collection
        embedding_model:    Embedding-Modell für die Frage
        top_k:              Anzahl der abzurufenden Chunks
        algorithm:          "similarity" oder "mmr"
        score_threshold:    Minimale Ähnlichkeit (None = kein Limit)
        llm_model:          LLM-Name in Ollama
        temperature:        Temperature (0.0 = deterministisch)
        system_prompt:      System-Prompt-Text

    Returns:
        tuple: (antwort, dauer_sek, n_chunks, quelldateien, chunk_texte, kontext_text)
            antwort         Generierte Antwort
            dauer_sek       Antwortzeit in Sekunden
            n_chunks        Anzahl abgerufener Chunks
            quelldateien    Kommagetrennte Quell-Dateipfade
            chunk_texte     Liste der Chunk-Texte (für BERTScore + ROUGE-L)
            kontext_text    Zusammengefügter Kontext (für CSV-Inspektion)
    """
    from langchain_ollama import OllamaEmbeddings, ChatOllama
    from langchain_chroma import Chroma

    start = time.time()
    chroma_path = str(SCRIPT_DIR / "chroma_eval" / collection_name)

    if not Path(chroma_path).exists():
        return (f"[FEHLER] Collection nicht gefunden: {collection_name}",
                0.0, 0, "", [], "")

    embeddings = OllamaEmbeddings(model=embedding_model)
    db = Chroma(
        collection_name=collection_name,
        persist_directory=chroma_path,
        embedding_function=embeddings
    )

    # Retrieval
    try:
        if algorithm == "mmr":
            docs = db.max_marginal_relevance_search(question, k=top_k)
        elif score_threshold is not None:
            docs = db.similarity_search_with_relevance_scores(question, k=top_k)
            docs = [d for d, score in docs if score >= score_threshold]
        else:
            docs = db.similarity_search(question, k=top_k)
    except Exception as e:
        return (f"[RETRIEVAL FEHLER] {e}", time.time() - start, 0, "", [], "")

    if not docs:
        return ("[KEIN KONTEXT GEFUNDEN]", time.time() - start, 0, "", [], "")

    # Chunk-Texte für Metriken (ungekürzt)
    chunk_texte = [doc.page_content for doc in docs]

    # Kontext für LLM (max 4000 Zeichen)
    max_chars = 4000
    separator = "\n\n"
    context_parts = []
    total_chars = 0
    for doc in docs:
        content = doc.page_content
        if total_chars + len(content) > max_chars:
            remaining = max_chars - total_chars
            if remaining > 100:
                context_parts.append(content[:remaining] + "...")
            break
        context_parts.append(content)
        total_chars += len(content)

    context = separator.join(context_parts)
    quelldateien = ", ".join(set(doc.metadata.get("source", "?") for doc in docs))

    # Generation
    full_prompt = f"""{system_prompt}

Kontext:
{context}

Frage: {question}

Antwort:"""

    try:
        llm = ChatOllama(model=llm_model, temperature=temperature)
        response = llm.invoke(full_prompt)
        antwort = response.content.strip()
    except Exception as e:
        return (f"[LLM FEHLER] {e}", time.time() - start, len(docs), quelldateien, chunk_texte, context)

    return (antwort, time.time() - start, len(docs), quelldateien, chunk_texte, context)


# ── Fortschritt laden ─────────────────────────────────────────────

def lade_erledigte_runs(csv_path: str) -> set:
    """
    Bereits erledigte Runs laden für Fortsetzung nach Abbruch.

    Erstellt einen eindeutigen Key aus allen Parametern + Frage-ID.
    Beim nächsten Start werden diese Runs übersprungen.

    Args:
        csv_path: Pfad zur bestehenden CSV

    Returns:
        Set von Tupeln (Parameter-Kombination + Frage-ID)
    """
    erledigte = set()
    path = Path(csv_path)
    if not path.exists():
        return erledigte

    import csv as csv_module
    with open(path, "r", encoding="utf-8") as f:
        reader = csv_module.DictReader(f)
        for row in reader:
            key = (
                row.get("embedding_model", ""), row.get("chunk_size", ""),
                row.get("overlap", ""), row.get("separator", ""),
                row.get("top_k", ""), row.get("algorithm", ""),
                row.get("score_threshold", ""), row.get("llm_model", ""),
                row.get("temperature", ""), row.get("system_prompt_name", ""),
                row.get("frage_id", "")
            )
            erledigte.add(key)
    return erledigte


# ── Nachbewertung ─────────────────────────────────────────────────

def nachbewertung_starten(csv_path: str):
    """
    Nachbewertung: zeigt nur Einträge mit score_manuell=None (Grauzone).

    Vereinfachte Skala:
        0  →  falsch (Ausweichantwort, Halluzination, falscher Chunk)
        1  →  teilweise richtig (Training-Wissen oder unvollständig)
        2  →  korrekt aus Chunk (RAG funktioniert)

    Auto-Scorer hat intern bereits 4/5 unterschieden — du bewertest
    nur die Qualität, nicht die Ursache.

    Args:
        csv_path: Pfad zur CSV mit None-Einträgen
    """
    import csv as csv_module
    from pathlib import Path

    path = Path(csv_path)
    if not path.exists():
        print(f"❌ CSV nicht gefunden: {csv_path}")
        return

    # Alle Zeilen laden
    with open(path, "r", encoding="utf-8") as f:
        daten = list(csv_module.DictReader(f))
        felder = daten[0].keys() if daten else []

    # None-Einträge finden
    none_eintraege = [
        (i, row) for i, row in enumerate(daten)
        if row.get("score_manuell", "") in ("", None)
        and row.get("auto_score", "") not in ("0",)
    ]

    if not none_eintraege:
        print("✅ Keine None-Einträge gefunden — alles bewertet!")
        return

    print(f"\n{'='*60}")
    print(f"📝 NACHBEWERTUNG — {Path(csv_path).name}")
    print(f"   {len(none_eintraege)} Einträge zu bewerten")
    print(f"   Skala: 0=Falsch | 1=Teilweise | 2=Korrekt")
    print(f"          s=Ueberspringen | q=Beenden")
    print(f"{'='*60}")

    bewertet = 0
    uebersprungen = 0

    try:
        for idx, (zeilen_nr, row) in enumerate(none_eintraege, 1):
            print(f"\n[{idx}/{len(none_eintraege)}] "
                  f"{row.get('embedding_model')} | "
                  f"c{row.get('chunk_size')} o{row.get('overlap')} | "
                  f"k{row.get('top_k')} | "
                  f"{row.get('llm_model')} t{row.get('temperature')} | "
                  f"{row.get('system_prompt_name')} | "
                  f"{row.get('frage_id')}")

            print(f"\n❓ FRAGE:\n{row.get('frage', '')}\n")
            print(f"✅ REFERENZ:\n{row.get('referenzantwort', '')}\n")
            print(f"🤖 SUSI:\n{row.get('generierte_antwort', '')}\n")

            # Metriken anzeigen
            bert = row.get('antwort_bert', '')
            rouge = row.get('antwort_rougeL', '')
            delta = row.get('delta', '')
            chunk_rouge = row.get('max_chunk_rougeL', '')

            if bert:
                print(f"📊 BERT: {float(bert):.3f} | "
                      f"ROUGE-L: {float(rouge) if rouge else 0:.3f} | "
                      f"Delta: {f'{float(delta):+.3f}' if delta else '0.000'} | "
                      f"ChunkROUGE: {float(chunk_rouge) if chunk_rouge else 0:.3f}")

            print(f"─"*60)
            print(f"0=Falsch | 1=Teilweise | 2=Korrekt | s=Skip | q=Beenden")

            while True:
                eingabe = input("Score: ").strip().lower()
                if eingabe in ("0", "1", "2"):
                    daten[zeilen_nr]["score_manuell"] = eingabe
                    bewertet += 1
                    break
                elif eingabe == "s":
                    uebersprungen += 1
                    break
                elif eingabe == "q":
                    raise KeyboardInterrupt
                else:
                    print("Bitte 0, 1, 2, s oder q eingeben.")

    except KeyboardInterrupt:
        print(f"\n⚠️  Unterbrochen nach {bewertet} Bewertungen")

    finally:
        # CSV zurückschreiben
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv_module.DictWriter(f, fieldnames=felder)
            writer.writeheader()
            writer.writerows(daten)

        print(f"\n✅ Gespeichert!")
        print(f"   Bewertet      : {bewertet}")
        print(f"   Übersprungen  : {uebersprungen}")
        print(f"   Noch offen    : {len(none_eintraege) - bewertet - uebersprungen}")



# ── Hauptfunktion ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SUSI Eval — Grid Run")
    parser.add_argument("--mode", choices=["smoke", "full"], default="smoke")
    parser.add_argument("--config", help="Pfad zur config.yaml")
    parser.add_argument("--manual", action="store_true")
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--llm", help="Nur dieses LLM testen")
    parser.add_argument("--embedding", help="Nur dieses Embedding-Modell testen")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--csv", help="CSV für --summary oder --nachbewertung")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--nachbewertung", action="store_true",
                        help="Nur None-Eintraege aus bestehender CSV nachbewerten")
    args = parser.parse_args()

    # Config laden
    config_path = find_config(args.config)
    config = load_config(config_path)

    # Nachbewertung — nur None-Einträge aus bestehender CSV
    if args.nachbewertung:
        if not args.csv:
            # Neueste CSV suchen
            results_dir = PROJECT_ROOT / "tools" / "evaluation" / "results"
            csvs = sorted(results_dir.glob("eval_*.csv"), reverse=True)
            if not csvs:
                print("❌ Keine CSV gefunden. --csv angeben.")
                return
            csv_path = str(csvs[0])
        else:
            csv_path = args.csv
        nachbewertung_starten(csv_path)
        return

    # Nur Zusammenfassung
    if args.summary:
        csv_path = args.csv
        if not csv_path:
            # Neueste CSV im results/ Ordner suchen
            results_dir = PROJECT_ROOT / "tools" / "evaluation" / "results"
            csvs = sorted(results_dir.glob("eval_*.csv"), reverse=True)
            if csvs:
                csv_path = str(csvs[0])
                print(f"📋 Neueste CSV: {csv_path}")
            else:
                print("Keine CSV gefunden. --csv angeben.")
                return
        drucke_zusammenfassung(csv_path)
        return

    # Fragen laden
    fragen_path = PROJECT_ROOT / config["meta"]["fragen_path"]
    fragen = lade_fragen(str(fragen_path), args.mode)

    # Kombinationen
    combos = get_all_combinations(config, args.llm, args.embedding)
    gesamt = len(combos) * len(fragen)

    # Output-Pfad mit Timestamp
    output_path = build_output_path(config, args.mode)

    print(f"\n{'='*60}")
    print(f"🚀 SUSI RAG Grid-Lauf")
    print(f"{'='*60}")
    print(f"   Modus          : {args.mode.upper()} ({len(fragen)} Fragen)")
    print(f"   Kombinationen  : {len(combos)}")
    print(f"   Gesamt Läufe   : {gesamt}")
    print(f"   Manuelle Wertung: {'JA' if args.manual else 'NEIN'}")
    print(f"   Output         : {output_path}")
    print(f"{'='*60}")

    if args.dry_run:
        print("\n🔍 DRY RUN — Keine Ausführung")
        return

    # Erledigte laden (Fortsetzung)
    erledigte = lade_erledigte_runs(output_path)
    if erledigte:
        print(f"\n♻️  {len(erledigte)} bereits erledigte Runs — werden übersprungen")

    writer = CSVWriter(output_path)
    run_nr = 0
    uebersprungen = 0
    fehler_count = 0
    auto_null_count = 0

    try:
        for combo in combos:
            (embedding, chunk_size, overlap, (sep_name, separators_list),
             top_k, algorithm_dict, score_threshold,
             llm, temperature, prompt_dict) = combo

            collection_name = get_collection_name(
                embedding["name"], chunk_size, overlap, sep_name
            )

            for frage_data in fragen:
                run_nr += 1

                resume_key = (
                    embedding["name"], str(chunk_size), str(overlap), sep_name,
                    str(top_k), algorithm_dict["name"], str(score_threshold),
                    llm["name"], str(temperature), prompt_dict["name"],
                    frage_data["id"]
                )

                if resume_key in erledigte:
                    uebersprungen += 1
                    continue

                kategorie = frage_data.get("kategorie", "?")
                print(f"\n[{run_nr}/{gesamt}] {embedding['name']} | c{chunk_size} o{overlap} | "
                      f"k{top_k} {algorithm_dict['name']} | {llm['name']} t{temperature} | "
                      f"{prompt_dict['name']} | {frage_data['id']}")
                print(f"  ❓ {frage_data['frage'][:80]}")

                # RAG-Anfrage
                try:
                    antwort, dauer, n_chunks, quellen, chunk_texte, kontext_text = rag_query(
                        question=frage_data["frage"],
                        collection_name=collection_name,
                        embedding_model=embedding["name"],
                        top_k=top_k,
                        algorithm=algorithm_dict["name"],
                        score_threshold=score_threshold,
                        llm_model=llm["name"],
                        temperature=temperature,
                        system_prompt=prompt_dict["text"]
                    )
                    fehler_text = ""
                    if antwort.startswith("[FEHLER]") or antwort.startswith("[LLM FEHLER]"):
                        fehler_text = antwort
                        antwort = ""
                        fehler_count += 1

                except Exception as e:
                    antwort = ""
                    dauer = 0.0
                    n_chunks = 0
                    quellen = ""
                    chunk_texte = []
                    kontext_text = ""
                    fehler_text = str(e)
                    fehler_count += 1

                print(f"  🤖 {antwort[:120]}" if len(antwort) > 120 else f"  🤖 {antwort}")
                print(f"  ⏱️  {dauer:.1f}s | {n_chunks} Chunks")

                # ── Scoring ───────────────────────────────────────────────
                # Auto-Scorer: berechnet Score 0-5 aus Metriken
                # Grauzone: nur dann manuell eingreifen

                # Schritt 1: Ausweichantwort prüfen (exakt, kein Teilstring)
                ausweich = pruefe_ausweichantwort(antwort) if antwort else None
                if ausweich == 0:
                    auto_null_count += 1

                # Schritt 2: Metriken berechnen
                bert_info = {}
                rouge_info = {}
                if antwort:
                    bert_info = berechne_bert_scores(
                        antwort=antwort,
                        referenz=frage_data["referenzantwort"],
                        chunks=chunk_texte
                    )
                    rouge_info = berechne_rouge_scores(
                        antwort=antwort,
                        referenz=frage_data["referenzantwort"],
                        chunks=chunk_texte
                    )
                    if bert_info.get("antwort_bert") is not None:
                        rouge_str = ""
                        if rouge_info.get("antwort_rougeL") is not None:
                            rouge_str = (f" | ROUGE-L: {rouge_info['antwort_rougeL']:.3f}"
                                        f" | ChunkROUGE: {rouge_info.get('max_chunk_rougeL', 0):.3f}")
                        print(f"  📐 BERT: {bert_info['antwort_bert']:.3f} | "
                              f"MaxChunk: {bert_info['max_chunk_bert']:.3f} | "
                              f"Delta: {bert_info['delta']:+.3f}{rouge_str}")

                # Schritt 3: Auto-Scorer (0-5 Skala)
                auto_result = berechne_auto_score(
                    antwort=antwort or "",
                    antwort_bert=bert_info.get("antwort_bert"),
                    max_chunk_bert=bert_info.get("max_chunk_bert"),
                    delta=bert_info.get("delta"),
                    antwort_rougeL=rouge_info.get("antwort_rougeL"),
                    max_chunk_rougeL=rouge_info.get("max_chunk_rougeL"),
                    auto_score_ausweich=ausweich
                )

                # Schritt 4: Score bestimmen
                score_man = None
                score_jud = None

                if args.manual and antwort:
                    try:
                        score_man = zeige_auto_score(
                            result=auto_result,
                            frage=frage_data["frage"],
                            referenz=frage_data["referenzantwort"],
                            antwort=antwort,
                            bert_info=bert_info,
                            rouge_info=rouge_info
                        )
                        if score_man == -1:
                            score_man = None
                    except KeyboardInterrupt:
                        print("\n⚠️  Manuelles Beenden — Ergebnisse werden gespeichert")
                        writer.close()
                        drucke_zusammenfassung(output_path)
                        return
                elif antwort and not auto_result["manuell"]:
                    # Automatisch bewertet — kein manueller Eingriff nötig
                    score_man = auto_result["score"]

                # Judge
                if args.judge and antwort and auto_result["manuell"]:
                    judge_cfg = config.get("evaluation", {}).get("judge_model", {})
                    if judge_cfg.get("enabled", False):
                        score_jud = score_mit_judge(
                            frage_data["frage"],
                            frage_data["referenzantwort"],
                            antwort,
                            judge_model=judge_cfg.get("model", "claude-sonnet-4-20250514")
                        )

                # Ergebnis speichern
                result = EvalResult(
                    run_id=str(uuid.uuid4())[:8],
                    timestamp=datetime.now().isoformat(),
                    embedding_model=embedding["name"],
                    chunk_size=chunk_size,
                    overlap=overlap,
                    separator=sep_name,
                    top_k=top_k,
                    algorithm=algorithm_dict["name"],
                    score_threshold=score_threshold,
                    llm_model=llm["name"],
                    temperature=temperature,
                    system_prompt_name=prompt_dict["name"],
                    frage_id=frage_data["id"],
                    kategorie=kategorie,
                    frage=frage_data["frage"],
                    referenzantwort=frage_data["referenzantwort"],
                    generierte_antwort=antwort,
                    kontext_text=kontext_text,
                    auto_score=ausweich,
                    score_manuell=score_man,
                    score_judge=score_jud,
                    antwort_bert=bert_info.get("antwort_bert"),
                    max_chunk_bert=bert_info.get("max_chunk_bert"),
                    delta=bert_info.get("delta"),
                    chunk_scores_bert=bert_info.get("chunk_scores_bert", ""),
                    antwort_rougeL=rouge_info.get("antwort_rougeL"),
                    max_chunk_rougeL=rouge_info.get("max_chunk_rougeL"),
                    chunk_scores_rougeL=rouge_info.get("chunk_scores_rougeL", ""),
                    antwortzeit_sek=round(dauer, 2),
                    kontext_chunks=n_chunks,
                    quelldateien=quellen,
                    fehler=fehler_text or bert_info.get("fehler", "")
                )
                writer.write(result)

    except KeyboardInterrupt:
        print("\n\n⚠️  Unterbrochen — bisher gespeicherte Ergebnisse sind sicher")

    finally:
        writer.close()

    # Abschluss
    print(f"\n{'='*60}")
    print(f"✅ Grid-Lauf abgeschlossen!")
    print(f"   Ausgeführt     : {run_nr - uebersprungen}")
    print(f"   Übersprungen   : {uebersprungen}")
    print(f"   Auto-Score 0   : {auto_null_count} Ausweichantworten")
    print(f"   Fehler         : {fehler_count}")
    print(f"   CSV            : {output_path}")

    drucke_zusammenfassung(output_path)

    # Meta-CSV generieren
    schreibe_meta(csv_path=output_path, config=config)

    print(f"\nZusammenfassung anzeigen:")
    print(f"  python tools/evaluation/grid_run.py --summary --csv {output_path}")


if __name__ == "__main__":
    main()