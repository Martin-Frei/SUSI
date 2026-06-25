"""
SUSI Evaluation — Grid Run
===========================
Haupt-Script: lädt Config + Gold-Set, iteriert alle Parameter-Kombinationen
und schreibt die Ergebnisse in eine CSV-Datei.

Voraussetzung: indexer.py wurde bereits ausgeführt (Collections existieren).

Jeder Lauf bekommt eine eigene CSV mit Timestamp im Namen:
    tools/evaluation/results/eval_20260524_1423_smoke.csv

Aufruf:
    # Smoke-Test (4 Fragen)
    python tools/evaluation/grid_run.py --mode smoke

    # Voller Grid-Lauf (293 Fragen, über Nacht)
    python tools/evaluation/grid_run.py --mode full

    # Dry-Run: Kombinationen zählen ohne auszuführen
    python tools/evaluation/grid_run.py --dry-run --mode full

    # Zusammenfassung einer bestehenden CSV
    python tools/evaluation/grid_run.py --summary --csv tools/evaluation/results/eval_xxx.csv

    # Nachbewertung (Grauzone-Einträge manuell bewerten)
    python tools/evaluation/grid_run.py --nachbewertung --csv tools/evaluation/results/eval_xxx.csv

Optionen:
    --mode smoke|full       Fragen-Set (Standard: smoke)
    --config PATH           Pfad zur config.yaml
    --manual                Manuelle Bewertung aktivieren
    --judge                 Judge-Modell aktivieren (braucht ANTHROPIC_API_KEY)
    --llm MODEL             Nur dieses LLM testen
    --embedding MODEL       Nur dieses Embedding-Modell testen
    --summary               Zusammenfassung anzeigen
    --csv PATH              CSV für --summary oder --nachbewertung
    --dry-run               Kombinationen zählen ohne auszuführen
    --nachbewertung         Nur None-Einträge aus bestehender CSV nachbewerten
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
from auto_scorer import berechne_auto_score, zeige_auto_score, berechne_qualitaets_score

PROJECT_ROOT = SCRIPT_DIR.parent.parent


# ── Fragen laden ──────────────────────────────────────────────────

def lade_fragen(fragen_path: str, mode: str) -> list:
    path = Path(fragen_path)
    if not path.exists():
        path = PROJECT_ROOT / fragen_path

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    fragen = []
    if mode == "smoke":
        for f in data["smoke_test"]["fragen"]:
            fragen.append(f)
    elif "full_run" in data:
        for f in data["full_run"]["fragen"]:
            if not f.get("id"):
                continue
            fragen.append(f)
    else:
        for kategorie, kat_data in data["full_evaluation"]["kategorien"].items():
            for f in kat_data["fragen"]:
                f["kategorie"] = kategorie
                fragen.append(f)

    for f in fragen:
        if "referenzantwort" not in f and "referenz" in f:
            f["referenzantwort"] = f["referenz"]

    return fragen


# ── Reranker-Kombinationen ────────────────────────────────────────

def get_reranker_combinations(config: dict) -> list:
    """
    Gibt alle Reranker-Configs zurück als Liste von Dicts.
    Jede Config enthält: active, model, top_n, top_k_filter

    Wenn kein reranker-Block in der Config: nur ohne Reranker.
    """
    reranker_cfg = config.get("reranker", {})
    configs = reranker_cfg.get("configs", [])

    if not configs:
        # Kein Reranker-Block — nur ohne Reranker
        return [{"active": False, "model": None, "top_n": None, "top_k_filter": None}]

    return configs


# ── Kombinationen ─────────────────────────────────────────────────

def get_all_combinations(config: dict,
                          filter_llm: str = None,
                          filter_embedding: str = None) -> list:
    """
    Alle aktiven Parameter-Kombinationen aus der config.yaml berechnen.
    Berücksichtigt Reranker-Configs mit top_k_filter.
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
    reranker_configs = get_reranker_combinations(config)

    combos = []
    base_combos = list(itertools.product(
        embeddings, chunk_sizes, overlaps, separators,
        top_k_values, algorithms, score_thresholds,
        llms, temperatures, prompts
    ))

    for combo in base_combos:
        (embedding, chunk_size, overlap, sep, top_k,
         algorithm, score_threshold, llm, temperature, prompt) = combo

        for reranker in reranker_configs:
            top_k_filter = reranker.get("top_k_filter")

            # top_k_filter prüfen — wenn gesetzt, nur passende k-Werte
            if top_k_filter is not None and top_k not in top_k_filter:
                continue

            combos.append((
                embedding, chunk_size, overlap, sep,
                top_k, algorithm, score_threshold,
                llm, temperature, prompt, reranker
            ))

    return combos


# ── Output-Pfad mit Timestamp ─────────────────────────────────────

def build_output_path(config: dict, mode: str) -> str:
    base = PROJECT_ROOT / "tools" / "evaluation" / "results"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"eval_{timestamp}_{mode}.csv"
    return str(base / filename)


# ── RAG-Anfrage mit optionalem Reranker ──────────────────────────

def rag_query(question: str, collection_name: str,
              embedding_model: str, top_k: int,
              algorithm: str, score_threshold: Optional[float],
              llm_model: str, temperature: float,
              system_prompt: str,
              reranker_cfg: dict = None,
              reranker_instance=None) -> tuple:
    """
    Eine RAG-Anfrage ausführen: Retrieval + optionaler Reranker + Generation.

    reranker_instance: bereits geladenes CrossEncoder-Objekt (aus dem Cache in main()).
                       Wenn übergeben, wird kein neues Modell geladen.

    Returns:
        tuple: (antwort, dauer_sek, n_chunks, quelldateien, chunk_texte,
                kontext_text, reranker_used)
    """
    from langchain_ollama import OllamaEmbeddings, ChatOllama
    from langchain_chroma import Chroma

    start = time.time()
    chroma_path = str(SCRIPT_DIR / "chroma_eval" / collection_name)

    if not Path(chroma_path).exists():
        return (f"[FEHLER] Collection nicht gefunden: {collection_name}",
                0.0, 0, "", [], "", False)

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
        return (f"[RETRIEVAL FEHLER] {e}", time.time() - start, 0, "", [], "", False)

    if not docs:
        return ("[KEIN KONTEXT GEFUNDEN]", time.time() - start, 0, "", [], "", False)

    # Reranker (optional) — nutzt gecachte Instanz aus main(), kein Nachladen
    reranker_used = False
    if reranker_cfg and reranker_cfg.get("active", False) and reranker_instance is not None:
        try:
            top_n = reranker_cfg.get("top_n", 3)
            pairs = [(question, doc.page_content) for doc in docs]
            scores = reranker_instance.predict(pairs)
            # float() konvertieren — amberoad gibt numpy-Arrays zurück, kein Scalar
            scores = [float(s) if not hasattr(s, '__len__') else float(s[0]) for s in scores]
            ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
            docs = [doc for _, doc in ranked[:top_n]]
            reranker_used = True
        except Exception as e:
            print(f"  ⚠️  Reranker Fehler: {e} — fahre ohne Reranker fort")

    # Chunk-Texte für Metriken
    chunk_texte = [doc.page_content for doc in docs]

    # Kontext für LLM (max 4000 Zeichen)
    max_chars = 4000
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

    context = "\n\n".join(context_parts)
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
        return (f"[LLM FEHLER] {e}", time.time() - start, len(docs),
                quelldateien, chunk_texte, context, reranker_used)

    return (antwort, time.time() - start, len(docs), quelldateien,
            chunk_texte, context, reranker_used)


# ── Fortschritt laden ─────────────────────────────────────────────

def lade_erledigte_runs(csv_path: str) -> set:
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
                row.get("reranker_active", ""), row.get("frage_id", "")
            )
            erledigte.add(key)
    return erledigte


# ── Nachbewertung ─────────────────────────────────────────────────

def nachbewertung_starten(csv_path: str):
    import csv as csv_module
    path = Path(csv_path)
    if not path.exists():
        print(f"❌ CSV nicht gefunden: {csv_path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        reader = csv_module.DictReader(f)
        felder = reader.fieldnames
        daten = list(reader)

    none_eintraege = [
        (i, row) for i, row in enumerate(daten)
        if row.get("score_manuell", "") in ("", "None", None)
        and row.get("generierte_antwort", "")
    ]

    print(f"\n📋 {len(none_eintraege)} Einträge ohne manuelle Bewertung")

    bewertet = 0
    uebersprungen = 0

    try:
        for zeilen_nr, row in none_eintraege:
            print(f"\n{'='*60}")
            print(f"❓ FRAGE:\n{row.get('frage', '')}\n")
            print(f"✅ REFERENZ:\n{row.get('referenzantwort', '')}\n")
            print(f"🤖 SUSI:\n{row.get('generierte_antwort', '')}\n")

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
            print(f"Qualitätsbewertung: 0=Falsch | 1=Teilweise | 2=Korrekt | s=Skip | q=Beenden")
            print(f"(Nur 0-2 gültig — Diagnosescores 3-5 gehören in auto_score, nicht hier)")

            while True:
                eingabe = input("Score: ").strip().lower()
                if eingabe in ("0", "1", "2"):
                    daten[zeilen_nr]["score_manuell"] = eingabe
                    bewertet += 1
                    break
                elif eingabe in ("3", "4", "5"):
                    print("⚠️  Diagnosescores (3-5) sind ungültig für score_manuell.")
                    print("   Bitte 0=Falsch, 1=Teilweise oder 2=Korrekt eingeben.")
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
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv_module.DictWriter(f, fieldnames=felder)
            writer.writeheader()
            writer.writerows(daten)

        print(f"\n✅ Gespeichert!")
        print(f"   Bewertet      : {bewertet}")
        print(f"   Übersprungen  : {uebersprungen}")


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
    parser.add_argument("--fragen", help="Pfad zur Fragen-JSON (überschreibt config)")
    parser.add_argument("--nachbewertung", action="store_true")
    args = parser.parse_args()

    config_path = find_config(args.config)
    config = load_config(config_path)

    if args.nachbewertung:
        if not args.csv:
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

    if args.summary:
        csv_path = args.csv
        if not csv_path:
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

    if args.fragen:
        fragen_path = Path(args.fragen)
        if not fragen_path.is_absolute():
            fragen_path = PROJECT_ROOT / args.fragen
    else:
        fragen_path = PROJECT_ROOT / config["meta"]["fragen_path"]
    fragen = lade_fragen(str(fragen_path), args.mode)

    combos = get_all_combinations(config, args.llm, args.embedding)
    gesamt = len(combos) * len(fragen)

    output_path = build_output_path(config, args.mode)

    # Reranker-Info für Anzeige
    reranker_configs = get_reranker_combinations(config)
    reranker_aktiv = any(r.get("active", False) for r in reranker_configs)

    print(f"\n{'='*60}")
    print(f"🚀 SUSI RAG Grid-Lauf — Lauf C")
    print(f"{'='*60}")
    print(f"   Modus          : {args.mode.upper()} ({len(fragen)} Fragen)")
    print(f"   Kombinationen  : {len(combos)}")
    print(f"   Gesamt Läufe   : {gesamt}")
    print(f"   Reranker       : {'JA' if reranker_aktiv else 'NEIN'}")
    print(f"   Manuelle Wertung: {'JA' if args.manual else 'NEIN (Auto-Scorer)'}")
    print(f"   Output         : {output_path}")
    print(f"{'='*60}")

    if args.dry_run:
        print("\n🔍 DRY RUN — Keine Ausführung")
        # Aufschlüsselung der Kombinationen
        print("\nKombinationen aufgeschlüsselt:")
        from collections import Counter
        reranker_counter = Counter()
        algo_counter = Counter()
        llm_counter = Counter()
        for combo in combos:
            (emb, cs, ov, sep, top_k, algo, st, llm, temp, prompt, reranker) = combo
            reranker_counter[f"reranker={'an' if reranker.get('active') else 'aus'}, k={top_k}"] += 1
            algo_counter[algo["name"]] += 1
            llm_counter[llm["name"]] += 1
        print(f"\n  LLM:")
        for k, v in llm_counter.items():
            print(f"    {k}: {v} Combos × {len(fragen)} Fragen = {v*len(fragen)} Runs")
        print(f"\n  Algorithmus:")
        for k, v in algo_counter.items():
            print(f"    {k}: {v} Combos")
        print(f"\n  Reranker + top_k:")
        for k, v in sorted(reranker_counter.items()):
            print(f"    {k}: {v} Combos")
        return

    erledigte = lade_erledigte_runs(output_path)
    if erledigte:
        print(f"\n♻️  {len(erledigte)} bereits erledigte Runs — werden übersprungen")

    # ── Reranker-Cache: einmal laden, für alle Runs wiederverwenden ──
    # Verhindert dass CrossEncoder() tausende Male neu instanziiert wird
    reranker_cache = {}
    from sentence_transformers import CrossEncoder
    for r_cfg in reranker_configs:
        if r_cfg.get("active", False) and r_cfg.get("model"):
            model_name = r_cfg["model"]
            if model_name not in reranker_cache:
                print(f"  🔁 Lade Reranker einmalig: {model_name}")
                reranker_cache[model_name] = CrossEncoder(model_name)
                print(f"  ✅ Reranker bereit: {model_name}")

    writer = CSVWriter(output_path)
    run_nr = 0
    uebersprungen = 0
    fehler_count = 0
    auto_null_count = 0

    try:
        for combo in combos:
            (embedding, chunk_size, overlap, (sep_name, separators_list),
             top_k, algorithm_dict, score_threshold,
             llm, temperature, prompt_dict, reranker_cfg) = combo

            collection_name = get_collection_name(
                embedding["name"], chunk_size, overlap, sep_name
            )

            reranker_label = "reranker=an" if reranker_cfg.get("active") else "reranker=aus"

            for frage_data in fragen:
                run_nr += 1

                resume_key = (
                    embedding["name"], str(chunk_size), str(overlap), sep_name,
                    str(top_k), algorithm_dict["name"], str(score_threshold),
                    llm["name"], str(temperature), prompt_dict["name"],
                    str(reranker_cfg.get("active", False)),
                    frage_data["id"]
                )

                if resume_key in erledigte:
                    uebersprungen += 1
                    continue

                kategorie = frage_data.get("kategorie", "?")
                print(f"\n[{run_nr}/{gesamt}] {embedding['name']} | c{chunk_size} | "
                      f"k{top_k} {algorithm_dict['name']} | {reranker_label} | "
                      f"{llm['name']} t{temperature} | {frage_data['id']}")
                print(f"  ❓ {frage_data['frage'][:80]}")

                try:
                    # Gecachte Reranker-Instanz holen (None wenn kein Reranker aktiv)
                    reranker_inst = reranker_cache.get(reranker_cfg.get("model")) if reranker_cfg.get("active") else None

                    result_tuple = rag_query(
                        question=frage_data["frage"],
                        collection_name=collection_name,
                        embedding_model=embedding["name"],
                        top_k=top_k,
                        algorithm=algorithm_dict["name"],
                        score_threshold=score_threshold,
                        llm_model=llm["name"],
                        temperature=temperature,
                        system_prompt=prompt_dict["text"],
                        reranker_cfg=reranker_cfg,
                        reranker_instance=reranker_inst
                    )
                    antwort, dauer, n_chunks, quellen, chunk_texte, kontext_text, reranker_used = result_tuple
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
                    reranker_used = False
                    fehler_text = str(e)
                    fehler_count += 1

                reranker_info = ""
                if reranker_cfg.get("active"):
                    top_n = reranker_cfg.get("top_n", 3)
                    reranker_info = f" | 🔁 {top_k}→{top_n}" if reranker_used else " | ⚠️ Reranker fehlgeschlagen"

                print(f"  🤖 {antwort[:120]}" if len(antwort) > 120 else f"  🤖 {antwort}")
                print(f"  ⏱️  {dauer:.1f}s | {n_chunks} Chunks{reranker_info}")

                # Scoring
                ausweich = pruefe_ausweichantwort(antwort) if antwort else None
                if ausweich == 0:
                    auto_null_count += 1

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

                auto_result = berechne_auto_score(
                    antwort=antwort or "",
                    antwort_bert=bert_info.get("antwort_bert"),
                    max_chunk_bert=bert_info.get("max_chunk_bert"),
                    delta=bert_info.get("delta"),
                    antwort_rougeL=rouge_info.get("antwort_rougeL"),
                    max_chunk_rougeL=rouge_info.get("max_chunk_rougeL"),
                    auto_score_ausweich=ausweich
                )

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
                    # Qualitätsscore (0/2/None) separat berechnen — nie auto_score (0-5) verwenden
                    score_man = berechne_qualitaets_score(
                        antwort=antwort,
                        antwort_bert=bert_info.get("antwort_bert"),
                        antwort_rougeL=rouge_info.get("antwort_rougeL"),
                        auto_score_ausweich=0 if auto_result.get("score") == 0 else None
                    )

                if args.judge and antwort and auto_result["manuell"]:
                    judge_cfg = config.get("evaluation", {}).get("judge_model", {})
                    if judge_cfg.get("enabled", False):
                        score_jud = score_mit_judge(
                            frage_data["frage"],
                            frage_data["referenzantwort"],
                            antwort,
                            judge_model=judge_cfg.get("model", "claude-sonnet-4-20250514")
                        )

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
                    auto_score=auto_result.get("score"),
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

    print(f"\n{'='*60}")
    print(f"✅ Grid-Lauf abgeschlossen!")
    print(f"   Ausgeführt     : {run_nr - uebersprungen}")
    print(f"   Übersprungen   : {uebersprungen}")
    print(f"   Auto-Score 0   : {auto_null_count} Ausweichantworten")
    print(f"   Fehler         : {fehler_count}")
    print(f"   CSV            : {output_path}")

    drucke_zusammenfassung(output_path)

    print(f"\nZusammenfassung anzeigen:")
    print(f"  python tools/evaluation/grid_run.py --summary --csv {output_path}")


if __name__ == "__main__":
    main()