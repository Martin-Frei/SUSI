"""
SUSI Evaluation — RAGAS + Haiku Judge Scorer
=============================================

Dieses Script ist die dritte Bewertungsstufe in der SUSI Eval-Pipeline.
Es arbeitet ausschließlich auf einer bestehenden CSV aus grid_run.py und
bewertet nur die Einträge die der Auto-Scorer nicht entscheiden konnte (Grauzone).

────────────────────────────────────────────────────────────────────────────────
WARUM DIESES SCRIPT?
────────────────────────────────────────────────────────────────────────────────

Der Auto-Scorer (auto_scorer.py) entscheidet anhand von ROUGE-L und BERT-Score.
Das funktioniert gut bei eindeutigen Fällen, aber SUSI antwortet oft paraphrasiert:
die Antwort ist inhaltlich korrekt, aber in anderen Worten als die Referenz.
Das führt zu niedrigem ROUGE-L → Grauzone, obwohl die Antwort gut ist.

In Lauf D wurden ~75% der Einträge als Grauzone markiert — damit sind
Aussagen wie "18.8% Fehlerrate bei lernen" statistisch nicht belastbar.

────────────────────────────────────────────────────────────────────────────────
DIE DREISTUFIGE PIPELINE (Gesamt-Überblick)
────────────────────────────────────────────────────────────────────────────────

    Stufe 1 — grid_run.py
        Generiert SUSI-Antworten für alle Parameterkombinationen.
        Schreibt CSV mit Frage, Referenz, Antwort, Chunks, ROUGE-L, BERT.

    Stufe 2 — auto_scorer.py
        Schnelle regelbasierte Bewertung (ROUGE-L + BERT-Schwellen).
        Klar korrekt  → Score 2 ✅
        Klar falsch   → Score 0 ❌
        Grauzone      → bleibt offen (~75% in Lauf D)

    Stufe 3 — ragas_scorer.py  ← DIESES SCRIPT
        Arbeitet nur auf Grauzone-Einträgen.
        Phase A: RAGAS (lokal, kein API, ~10-15 Min für 600 Zeilen)
            Faithfulness   → Ist die Antwort aus den Chunks ableitbar?
            Answer Relevancy → Beantwortet die Antwort die Frage?
        Phase B: Haiku Judge (nur für Rest der Grauzone nach Phase A)
            LLM-basierte Bewertung via Anthropic API (claude-haiku-4-5)
            Frage + Referenz + Antwort → 0/1/2
            Kosten: ~$0.10-0.50 pro Lauf (Haiku ist sehr günstig)

────────────────────────────────────────────────────────────────────────────────
WARUM NICHT IM LIVE-SYSTEM?
────────────────────────────────────────────────────────────────────────────────

RAGAS macht intern LLM-Calls → zu langsam für Live-Antworten.
Haiku-Calls kosten Geld pro Anfrage.
Dieses Script ist reines Offline-Eval-Werkzeug — es berührt nie query.py.

────────────────────────────────────────────────────────────────────────────────
NEUE CSV-SPALTEN (werden zur bestehenden CSV hinzugefügt)
────────────────────────────────────────────────────────────────────────────────

    ragas_faithfulness      float 0.0-1.0   Antwort aus Chunks ableitbar?
    ragas_answer_relevancy  float 0.0-1.0   Antwort beantwortet die Frage?
    ragas_score             float 0.0-1.0   Mittelwert beider RAGAS-Metriken
    haiku_score             int   0/1/2     Haiku-Urteil (nur wenn RAGAS unklar)
    final_score             int   0/1/2     Finaler Score (auto → ragas → haiku)
    bewertung_quelle        str             Wer hat bewertet (auto/ragas/haiku/grauzone)

────────────────────────────────────────────────────────────────────────────────
AUFRUF
────────────────────────────────────────────────────────────────────────────────

    # Nur RAGAS (kein Haiku, kein API-Key nötig)
    python tools/evaluation/ragas_scorer.py --csv eval_lauf_d.csv

    # RAGAS + Haiku für restliche Grauzone (ANTHROPIC_API_KEY muss gesetzt sein)
    python tools/evaluation/ragas_scorer.py --csv eval_lauf_d.csv --haiku

    # Dry-Run: nur Grauzone zählen, nichts bewerten
    python tools/evaluation/ragas_scorer.py --csv eval_lauf_d.csv --dry-run

    # RAGAS-Schwelle anpassen (Standard: 0.5)
    python tools/evaluation/ragas_scorer.py --csv eval_lauf_d.csv --ragas-threshold 0.6

    # Zusammenfassung einer bereits bewerteten CSV anzeigen
    python tools/evaluation/ragas_scorer.py --csv eval_lauf_d_ragas.csv --summary

────────────────────────────────────────────────────────────────────────────────
ABHÄNGIGKEITEN
────────────────────────────────────────────────────────────────────────────────

    pip install ragas                   RAGAS Framework
    pip install anthropic               Haiku Judge (optional, nur mit --haiku)
    pip install langchain-community     RAGAS braucht LangChain-kompatible LLMs
    pip install langchain-ollama        Ollama als RAGAS-Backend (lokal, kostenlos)

    RAGAS nutzt intern ein LLM für Faithfulness/Relevancy.
    Standard-Backend hier: Ollama mit qwen2.5:7b (lokal, GDPR-konform).
    Kein OpenAI-Key nötig.

    Für Haiku Judge zusätzlich:
    ANTHROPIC_API_KEY=sk-ant-... (in .env oder Umgebungsvariable)

────────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import csv
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
load_dotenv()  # liest .env aus Projektroot (ANTHROPIC_API_KEY etc.)

csv.field_size_limit(10_000_000)

# ── Pfade ─────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# ── Schwellen ─────────────────────────────────────────────────────

RAGAS_SCHWELLE_KORREKT = 0.6       # Über dieser Schwelle → Score 2
RAGAS_SCHWELLE_FALSCH = 0.3        # Unter dieser Schwelle → Score 0
# Dazwischen → Score 1 (teilweise) oder weiter zu Haiku

HAIKU_MODELL = "claude-haiku-4-5-20251001"

HAIKU_SYSTEM_PROMPT = """Du bist ein Evaluator für ein RAG-System (SUSI).
Deine Aufgabe: Bewerte ob die generierte Antwort die Frage korrekt beantwortet.
Nutze dafür die Referenzantwort als Maßstab.

Antworte NUR mit einer einzigen Zahl:
0 = Falsch oder Ausweichantwort
1 = Teilweise korrekt (wichtige Details fehlen oder sind ungenau)
2 = Korrekt (inhaltlich äquivalent zur Referenz, auch wenn andere Wortwahl)

Keine Erklärung. Nur die Zahl."""

# ── Grauzone erkennen ─────────────────────────────────────────────

def ist_grauzone(row: dict) -> bool:
    """
    Prüft ob ein CSV-Eintrag noch keine gültige Bewertung hat.
    Grauzone = auto_score ist leer UND score_manuell ist leer.
    """
    auto = row.get("auto_score", "").strip()
    manuell = row.get("score_manuell", "").strip()
    final = row.get("final_score", "").strip()

    # Bereits durch dieses Script bewertet
    if final:
        return False

    # Auto-Scorer hat entschieden
    if auto and auto not in ("", "None"):
        return False

    # Manuell bewertet
    if manuell and manuell in ("0", "1", "2"):
        return False

    return True


def get_final_score_aus_auto(row: dict) -> Optional[int]:
    """
    Liest den Auto-Score und mappt ihn auf die 0/1/2 Qualitätsskala.

    Auto-Scorer Skala (0-5, Diagnoseskala):
        0 = Ausweichantwort   → Qualität 0
        1 = Halluzination     → Qualität 0
        2 = Training korrekt  → Qualität 1 (teilweise — kein RAG-Treffer)
        3 = RAG korrekt       → Qualität 2
        4 = Generation-Fehler → Qualität 0
        5 = Falscher Chunk    → Qualität 0
    """
    auto = row.get("auto_score", "").strip()
    if not auto or auto in ("", "None"):
        return None

    mapping = {"0": 0, "1": 0, "2": 1, "3": 2, "4": 0, "5": 0}
    return mapping.get(auto)



# ── RAGAS Setup ───────────────────────────────────────────────────

def setup_ragas(ollama_modell: str = "qwen2.5:7b"):
    """
    Initialisiert RAGAS mit lokalem Ollama-Backend.
    Kein OpenAI-Key nötig, GDPR-konform, läuft komplett lokal.

    RAGAS braucht:
    - Ein LLM für Faithfulness (prüft ob Antwort aus Chunks ableitbar)
    - Ein Embedding-Modell für Answer Relevancy (prüft ob Antwort zur Frage passt)

    Verwendet die neue RAGAS API (>= 0.2):
    - from ragas.metrics.collections statt ragas.metrics
    - llm_factory + OllamaChat statt LangchainLLMWrapper
    - HuggingFaceEmbeddings statt LangchainEmbeddingsWrapper
    """
    try:
        from ragas import evaluate
        # Alte ragas.metrics API -- kompatibel mit LangchainLLMWrapper + Ollama
        # ragas.metrics.collections erfordert llm_factory (OpenAI-only), daher nicht nutzbar
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            from ragas.metrics import faithfulness, answer_relevancy  # type: ignore[attr-defined]
        from ragas.llms import LangchainLLMWrapper                    # type: ignore[attr-defined]
        from ragas.embeddings import LangchainEmbeddingsWrapper        # type: ignore[attr-defined]
        from langchain_ollama import ChatOllama, OllamaEmbeddings

        llm = LangchainLLMWrapper(ChatOllama(model=ollama_modell, temperature=0.0))
        embeddings = LangchainEmbeddingsWrapper(OllamaEmbeddings(model="bge-m3"))

        # Metrics mit LLM + Embeddings verknuepfen
        faithfulness.llm = llm
        answer_relevancy.llm = llm
        answer_relevancy.embeddings = embeddings

        print(f"🔧 RAGAS initialisiert mit Ollama/{ollama_modell} + bge-m3")

        return {
            "evaluate": evaluate,
            "metrics": [faithfulness, answer_relevancy],
            "llm": llm,
            "embeddings": embeddings,
            "ok": True
        }

    except ImportError as e:
        print(f"❌ RAGAS Import-Fehler: {e}")
        print("   Installieren: pip install ragas langchain-ollama")
        return {"ok": False}



def bewerte_mit_ragas(ragas_ctx: dict, frage: str, antwort: str,
                      chunks: str, referenz: str) -> dict:
    """
    Bewertet eine einzelne Antwort mit RAGAS.

    Args:
        ragas_ctx:  RAGAS-Kontext aus setup_ragas()
        frage:      Die Originalfrage
        antwort:    SUSIs generierte Antwort
        chunks:     Die retrieved Chunks (kontext_text aus CSV)
        referenz:   Die Referenzantwort aus dem Gold-Set

    Returns:
        dict mit faithfulness, answer_relevancy, ragas_score, fehler
    """
    try:
        from datasets import Dataset

        # Chunks als Liste — RAGAS erwartet List[List[str]]
        chunk_liste = [c.strip() for c in chunks.split("\n---\n") if c.strip()]
        if not chunk_liste:
            chunk_liste = [chunks[:2000]]  # Fallback: ganzer Text als ein Chunk

        dataset = Dataset.from_dict({
            "question":  [frage],
            "answer":    [antwort],
            "contexts":  [chunk_liste],
            "ground_truth": [referenz],
        })

        result = ragas_ctx["evaluate"](
            dataset=dataset,
            metrics=ragas_ctx["metrics"],
            llm=ragas_ctx["llm"],
            embeddings=ragas_ctx["embeddings"],
        )

        # RAGAS gibt manchmal Listen zurueck statt Skalare
        # z.B. result["faithfulness"] = [0.8] statt 0.8
        def zu_float(val):
            if isinstance(val, (list, tuple)):
                val = val[0] if val else 0.0
            return float(val)

        faith = zu_float(result["faithfulness"])
        relev = zu_float(result["answer_relevancy"])
        score = round((faith + relev) / 2, 4)

        return {
            "faithfulness": faith,
            "answer_relevancy": relev,
            "ragas_score": score,
            "fehler": ""
        }

    except Exception as e:
        return {
            "faithfulness": None,
            "answer_relevancy": None,
            "ragas_score": None,
            "fehler": str(e)[:200]
        }


# ── Haiku Judge ───────────────────────────────────────────────────

def setup_haiku() -> dict:
    """
    Initialisiert den Haiku Judge via Anthropic API.
    Braucht ANTHROPIC_API_KEY als Umgebungsvariable oder in .env.
    """
    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            print("❌ ANTHROPIC_API_KEY nicht gesetzt")
            return {"ok": False}

        client = anthropic.Anthropic(api_key=api_key)
        print(f"🤖 Haiku Judge initialisiert ({HAIKU_MODELL})")
        return {"client": client, "ok": True}

    except ImportError:
        print("❌ anthropic nicht installiert: pip install anthropic")
        return {"ok": False}


def bewerte_mit_haiku(haiku_ctx: dict, frage: str, antwort: str, referenz: str) -> dict:
    """
    Bewertet eine Antwort via claude-haiku-4-5.

    Prompt-Strategie:
    - System: Klare Rolle + nur Zahl zurückgeben
    - User: Frage + Referenz + Antwort strukturiert
    - Sehr kurze max_tokens (10) — wir wollen nur "0", "1" oder "2"

    Kosten: Haiku ist ~25x günstiger als Sonnet.
    Bei 200 Calls: ca. $0.05-0.15.
    """
    try:
        user_prompt = (
            f"FRAGE:\n{frage}\n\n"
            f"REFERENZANTWORT:\n{referenz}\n\n"
            f"GENERIERTE ANTWORT:\n{antwort}\n\n"
            f"Score (0/1/2):"
        )

        response = haiku_ctx["client"].messages.create(
            model=HAIKU_MODELL,
            max_tokens=10,
            system=HAIKU_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}]
        )

        antwort_text = response.content[0].text.strip()

        # Robustes Parsing — nur erste Ziffer extrahieren
        score = None
        for zeichen in antwort_text:
            if zeichen in ("0", "1", "2"):
                score = int(zeichen)
                break

        if score is None:
            return {"haiku_score": None, "fehler": f"Unklare Antwort: '{antwort_text}'"}

        return {"haiku_score": score, "fehler": ""}

    except Exception as e:
        return {"haiku_score": None, "fehler": str(e)[:200]}


# ── Score-Entscheidung ────────────────────────────────────────────

def ragas_zu_qualitaetsscore(ragas_score: float) -> Optional[int]:
    """
    Mappt RAGAS-Score (0.0-1.0) auf Qualitätsskala (0/1/2).

    Schwellen (konfigurierbar via --ragas-threshold):
        >= 0.6  → 2 (korrekt)
        <= 0.3  → 0 (falsch)
        dazwischen → None (weiter zu Haiku)
    """
    if ragas_score is None:
        return None
    if ragas_score >= RAGAS_SCHWELLE_KORREKT:
        return 2
    if ragas_score <= RAGAS_SCHWELLE_FALSCH:
        return 0
    return None   # Mittelbereich → Haiku entscheidet


# ── CSV verarbeiten ───────────────────────────────────────────────

def verarbeite_csv(
    csv_path: Path,
    ragas_ctx: dict,
    haiku_ctx: dict,
    mit_haiku: bool,
    dry_run: bool
) -> Path:
    """
    Hauptfunktion: liest CSV, bewertet Grauzone-Einträge, schreibt neue CSV.

    Strategie:
    1. Alle Zeilen einlesen
    2. Grauzone-Einträge identifizieren
    3. Für jede Grauzone-Zeile: RAGAS → evtl. Haiku
    4. Neue CSV mit zusätzlichen Spalten schreiben

    Output-Datei: original_name_ragas_YYYYMMDD_HHMM.csv
    """

    # ── Einlesen ──
    with open(csv_path, "r", encoding="utf-8") as f:
        leser = csv.DictReader(f)
        alle_zeilen = list(leser)
        original_felder = list(leser.fieldnames or [])

    grauzone_zeilen = [z for z in alle_zeilen if ist_grauzone(z)]
    auto_zeilen = [z for z in alle_zeilen if not ist_grauzone(z)]

    print(f"\n{'='*60}")
    print(f"📂 CSV: {csv_path.name}")
    print(f"   Gesamt:       {len(alle_zeilen)}")
    print(f"   Auto bewertet:{len(auto_zeilen)} ({len(auto_zeilen)/len(alle_zeilen)*100:.1f}%)")
    print(f"   Grauzone:     {len(grauzone_zeilen)} ({len(grauzone_zeilen)/len(alle_zeilen)*100:.1f}%)")
    print(f"{'='*60}\n")

    if dry_run:
        print("🔍 Dry-Run — keine Bewertung durchgeführt.")
        return csv_path

    if not grauzone_zeilen:
        print("✅ Keine Grauzone-Einträge — nichts zu tun.")
        return csv_path

    # ── Neue Spalten ──
    neue_felder = original_felder + [
        "ragas_faithfulness",
        "ragas_answer_relevancy",
        "ragas_score",
        "haiku_score",
        "final_score",
        "bewertung_quelle",
    ]

    # ── Output-Datei ──
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_path = csv_path.parent / f"{csv_path.stem}_ragas_{timestamp}.csv"

    # ── Statistik ──
    stats = {
        "grauzone_gesamt": len(grauzone_zeilen),
        "ragas_korrekt": 0,
        "ragas_falsch": 0,
        "ragas_unklar": 0,
        "haiku_bewertet": 0,
        "final_grauzone": 0,
        "fehler": 0,
    }

    # ── Grauzone bewerten ──
    grauzone_ergebnisse = {}   # row-Index → neue Felder

    print(f"🚀 Starte RAGAS-Bewertung für {len(grauzone_zeilen)} Einträge...\n")

    for i, zeile in enumerate(grauzone_zeilen):
        frage    = zeile.get("frage", "")
        antwort  = zeile.get("generierte_antwort", "")
        chunks   = zeile.get("kontext_text", "")
        referenz = zeile.get("referenzantwort", "")

        zid = zeile.get("id", f"row_{i}")
        print(f"[{i+1}/{len(grauzone_zeilen)}] {zid[:50]}", end=" ", flush=True)

        neues = {
            "ragas_faithfulness": "",
            "ragas_answer_relevancy": "",
            "ragas_score": "",
            "haiku_score": "",
            "final_score": "",
            "bewertung_quelle": "grauzone",
        }

        # Phase A — RAGAS
        if ragas_ctx["ok"]:
            t0 = time.time()
            ragas_result = bewerte_mit_ragas(ragas_ctx, frage, antwort, chunks, referenz)
            dauer = time.time() - t0

            if ragas_result["fehler"]:
                print(f"⚠️  RAGAS-Fehler: {ragas_result['fehler'][:60]}")
                stats["fehler"] += 1
            else:
                rs = ragas_result["ragas_score"]
                neues["ragas_faithfulness"] = str(round(ragas_result["faithfulness"], 4))
                neues["ragas_answer_relevancy"] = str(round(ragas_result["answer_relevancy"], 4))
                neues["ragas_score"] = str(round(rs, 4))

                q_score = ragas_zu_qualitaetsscore(rs)

                if q_score == 2:
                    neues["final_score"] = "2"
                    neues["bewertung_quelle"] = "ragas"
                    stats["ragas_korrekt"] += 1
                    print(f"✅ RAGAS={rs:.3f} → Score 2  ({dauer:.1f}s)")
                elif q_score == 0:
                    neues["final_score"] = "0"
                    neues["bewertung_quelle"] = "ragas"
                    stats["ragas_falsch"] += 1
                    print(f"❌ RAGAS={rs:.3f} → Score 0  ({dauer:.1f}s)")
                else:
                    # Mittelbereich → Haiku
                    stats["ragas_unklar"] += 1
                    print(f"🔶 RAGAS={rs:.3f} → unklar  ({dauer:.1f}s)", end=" ")

                    # Phase B — Haiku
                    if mit_haiku and haiku_ctx["ok"]:
                        haiku_result = bewerte_mit_haiku(haiku_ctx, frage, antwort, referenz)
                        if haiku_result["fehler"]:
                            print(f"⚠️  Haiku-Fehler: {haiku_result['fehler'][:40]}")
                            stats["fehler"] += 1
                        else:
                            hs = haiku_result["haiku_score"]
                            neues["haiku_score"] = str(hs)
                            neues["final_score"] = str(hs)
                            neues["bewertung_quelle"] = "haiku"
                            stats["haiku_bewertet"] += 1
                            print(f"→ Haiku={hs}")
                    else:
                        print()  # Zeilenumbruch
                        stats["final_grauzone"] += 1
        else:
            # RAGAS nicht verfügbar — direkt zu Haiku
            print(f"⚠️  RAGAS nicht verfügbar", end=" ")
            if mit_haiku and haiku_ctx["ok"]:
                haiku_result = bewerte_mit_haiku(haiku_ctx, frage, antwort, referenz)
                if not haiku_result["fehler"]:
                    hs = haiku_result["haiku_score"]
                    neues["haiku_score"] = str(hs)
                    neues["final_score"] = str(hs)
                    neues["bewertung_quelle"] = "haiku"
                    stats["haiku_bewertet"] += 1
                    print(f"→ Haiku={hs}")
            else:
                print()
                stats["final_grauzone"] += 1

        grauzone_ergebnisse[id(zeile)] = neues

    # ── CSV schreiben ──
    print(f"\n💾 Schreibe Output: {output_path.name}")

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=neue_felder, extrasaction="ignore")
        writer.writeheader()

        for zeile in alle_zeilen:
            neue_zeile = dict(zeile)

            if id(zeile) in grauzone_ergebnisse:
                neue_zeile.update(grauzone_ergebnisse[id(zeile)])
            else:
                # Auto-bewertete Zeile — final_score aus Auto-Score ableiten
                auto_final = get_final_score_aus_auto(zeile)
                neue_zeile["ragas_faithfulness"] = ""
                neue_zeile["ragas_answer_relevancy"] = ""
                neue_zeile["ragas_score"] = ""
                neue_zeile["haiku_score"] = ""
                neue_zeile["final_score"] = str(auto_final) if auto_final is not None else ""
                neue_zeile["bewertung_quelle"] = "auto" if auto_final is not None else zeile.get("bewertung_quelle", "")

            writer.writerow(neue_zeile)

    # ── Zusammenfassung ──
    drucke_zusammenfassung(stats, len(alle_zeilen))

    return output_path


def drucke_zusammenfassung(stats: dict, gesamt: int):
    """Druckt eine übersichtliche Zusammenfassung nach dem Lauf."""

    grau = stats["grauzone_gesamt"]
    print(f"\n{'='*60}")
    print(f"📊 RAGAS SCORER — ZUSAMMENFASSUNG")
    print(f"{'='*60}")
    print(f"   Grauzone-Einträge:    {grau}")
    print(f"   ├─ RAGAS korrekt:     {stats['ragas_korrekt']}  ({stats['ragas_korrekt']/grau*100:.1f}%)")
    print(f"   ├─ RAGAS falsch:      {stats['ragas_falsch']}  ({stats['ragas_falsch']/grau*100:.1f}%)")
    print(f"   ├─ Haiku bewertet:    {stats['haiku_bewertet']}  ({stats['haiku_bewertet']/grau*100:.1f}%)")
    print(f"   ├─ Noch Grauzone:     {stats['final_grauzone']}  ({stats['final_grauzone']/grau*100:.1f}%)")
    print(f"   └─ Fehler:            {stats['fehler']}")
    print(f"{'='*60}")

    bewertet = stats["ragas_korrekt"] + stats["ragas_falsch"] + stats["haiku_bewertet"]
    print(f"   Grauzone gelöst:      {bewertet}/{grau} ({bewertet/grau*100:.1f}%)")
    print(f"{'='*60}\n")


def drucke_summary_csv(csv_path: Path):
    """Liest eine bereits bewertete CSV und druckt Statistiken."""

    with open(csv_path, "r", encoding="utf-8") as f:
        zeilen = list(csv.DictReader(f))

    quellen = {}
    scores = {"0": 0, "1": 0, "2": 0}

    for z in zeilen:
        q = z.get("bewertung_quelle", "unbekannt")
        quellen[q] = quellen.get(q, 0) + 1
        fs = str(z.get("final_score", "")).strip()
        if fs in scores:
            scores[fs] += 1

    print(f"\n{'='*60}")
    print(f"📊 SUMMARY: {csv_path.name}")
    print(f"{'='*60}")
    print(f"   Gesamt: {len(zeilen)}")
    print(f"\n   Bewertungsquellen:")
    for q, n in sorted(quellen.items(), key=lambda x: -x[1]):
        print(f"   ├─ {q:<15} {n} ({n/len(zeilen)*100:.1f}%)")
    print(f"\n   Final-Score Verteilung:")
    for s, n in scores.items():
        label = {"0": "Falsch", "1": "Teilweise", "2": "Korrekt"}[s]
        print(f"   ├─ Score {s} ({label:<10}) {n} ({n/len(zeilen)*100:.1f}%)")

    bewertet = sum(1 for z in zeilen if str(z.get("final_score", "")).strip())
    korrekt = scores["2"]
    if bewertet > 0:
        print(f"\n   Korrektheit (bewertet): {korrekt}/{bewertet} = {korrekt/bewertet*100:.1f}%")
    print(f"{'='*60}\n")


# ── CLI ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="SUSI RAGAS + Haiku Scorer — Grauzone-Bewertung",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python ragas_scorer.py --csv eval_lauf_d.csv
  python ragas_scorer.py --csv eval_lauf_d.csv --haiku
  python ragas_scorer.py --csv eval_lauf_d.csv --dry-run
  python ragas_scorer.py --csv eval_lauf_d_ragas_2026.csv --summary
        """
    )

    parser.add_argument("--csv",              required=True,        help="Pfad zur Eval-CSV")
    parser.add_argument("--haiku",            action="store_true",  help="Haiku Judge für Rest-Grauzone aktivieren")
    parser.add_argument("--dry-run",          action="store_true",  help="Nur zählen, nicht bewerten")
    parser.add_argument("--summary",          action="store_true",  help="Zusammenfassung einer bewerteten CSV")
    parser.add_argument("--ragas-threshold",  type=float, default=0.5, help="RAGAS-Schwelle für korrekt (Standard: 0.5)")
    parser.add_argument("--ollama-modell",    default="qwen2.5:7b", help="Ollama-Modell für RAGAS (Standard: qwen2.5:7b)")

    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"❌ CSV nicht gefunden: {csv_path}")
        sys.exit(1)

    # Summary-Modus
    if args.summary:
        drucke_summary_csv(csv_path)
        return

    # Schwellen übernehmen
    global RAGAS_SCHWELLE_KORREKT, RAGAS_SCHWELLE_FALSCH
    RAGAS_SCHWELLE_KORREKT = args.ragas_threshold
    RAGAS_SCHWELLE_FALSCH = args.ragas_threshold - 0.3

    print(f"\n🔧 RAGAS Schwellen: korrekt>={RAGAS_SCHWELLE_KORREKT:.2f}, falsch<={RAGAS_SCHWELLE_FALSCH:.2f}")

    # RAGAS initialisieren
    ragas_ctx = setup_ragas(ollama_modell=args.ollama_modell)

    # Haiku initialisieren (optional)
    haiku_ctx = {"ok": False}
    if args.haiku:
        haiku_ctx = setup_haiku()

    # Verarbeiten
    output = verarbeite_csv(
        csv_path=csv_path,
        ragas_ctx=ragas_ctx,
        haiku_ctx=haiku_ctx,
        mit_haiku=args.haiku,
        dry_run=args.dry_run,
    )

    if not args.dry_run:
        print(f"✅ Fertig: {output}")


if __name__ == "__main__":
    main()