"""
SUSI Evaluation — CSV Analyse
==============================
Legt die CSV-Ergebnisse nach einzelnen Parametern auseinander.

Score-Berechnung (wichtig für Tutor-Fragen):
    Score = Durchschnitt aller Einträge pro Parameter-Gruppe
    Einbezogen: manueller Score (0/1/2) UND Auto-Score 0 (Ausweichantworten)
              UND final_score (RAGAS/Haiku-Bewertung aus ragas_scorer.py)
    Ausgeschlossen: Einträge ohne jeglichen Score
    
    Priorität: auto_score=0 > score_manuell > final_score
    
    Skala: 0.0 = alle falsch, 1.0 = alle teilweise, 2.0 = alle korrekt
    
    Beispiel bge-m3:
        75 Auto-Score 0  →  75 × 0 =   0
       200 manuell 0     →  200 × 0 =   0
        50 manuell 1     →  50 × 1 =  50
       134 manuell 2     →  134 × 2 = 268
        ──────────────────────────────────
        459 Einträge, Summe 318 → Score = 318/459 = 0.693

Aufruf:
    python tools/evaluation/analyse_csv.py --csv tools/evaluation/results/eval_20260524_2115_smoke.csv
    python tools/evaluation/analyse_csv.py --csv tools/evaluation/results/eval_20260524_2115_smoke.csv --korrektur
    python tools/evaluation/analyse_csv.py --csv tools/evaluation/results/eval_20260524_2115_smoke.csv --fix RUN_ID 2
"""

import csv
csv.field_size_limit(10_000_000)
import argparse
import statistics
from pathlib import Path
from collections import defaultdict


def lade_csv(csv_path: str) -> list:
    """CSV laden und als Liste von Dicts zurückgeben."""
    with open(csv_path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# Mapping Diagnoseskala (0-5) auf Qualitaetsskala (0-2)
# auto_score=0 Ausweichantwort    -> Qualitaet 0
# auto_score=1 Halluzination      -> Qualitaet 0
# auto_score=2 Training korrekt   -> Qualitaet 1 (richtige Antwort, falscher Weg)
# auto_score=3 RAG korrekt        -> Qualitaet 2
# auto_score=4 Generation-Problem -> Qualitaet 0
# auto_score=5 Falscher Chunk     -> Qualitaet 0
AUTO_SCORE_MAPPING = {"0": 0.0, "1": 0.0, "2": 1.0, "3": 2.0, "4": 0.0, "5": 0.0}


def get_effektiver_score(row: dict):
    """
    Effektiven Score einer Zeile bestimmen.

    Reihenfolge:
        1. score_manuell (0/1/2) — hoehere Prioritaet als auto
        2. final_score (RAGAS/Haiku, 0/1/2)
        3. auto_score (0-5) via Mapping auf Qualitaetsskala
        4. Kein Score -> None (wird ausgeschlossen)

    Mapping Diagnoseskala -> Qualitaetsskala:
        0 Ausweichantwort    -> 0
        1 Halluzination      -> 0
        2 Training korrekt   -> 1  (richtige Antwort, falscher Weg)
        3 RAG korrekt        -> 2
        4 Generation-Problem -> 0
        5 Falscher Chunk     -> 0
    """
    auto = row.get("auto_score", "").strip()
    manuell = row.get("score_manuell", "").strip()
    final = row.get("final_score", "").strip()

    # Manuell hat hoechste Prioritaet
    if manuell not in ("", None, "-1"):
        try:
            return float(manuell)
        except ValueError:
            pass

    # RAGAS/Haiku Score
    if final not in ("", None):
        try:
            return float(final)
        except ValueError:
            pass

    # Auto-Score via Mapping
    if auto in AUTO_SCORE_MAPPING:
        return AUTO_SCORE_MAPPING[auto]

    return None


def analysiere_parameter(daten: list, parameter: str, titel: str):
    """
    Analysiert einen einzelnen Parameter und zeigt Score pro Wert.

    Score = Durchschnitt (manuell + Auto-Score 0) / Gesamteinträge
    Skala: 0.0 (alle falsch) bis 2.0 (alle korrekt)

    Args:
        daten:      Liste von CSV-Zeilen
        parameter:  Spaltenname in der CSV
        titel:      Anzeige-Titel
    """
    gruppen = defaultdict(list)
    auto_nullen = defaultdict(int)
    bert_scores = defaultdict(list)
    rouge_scores = defaultdict(list)

    for row in daten:
        wert = row.get(parameter, "?")
        score = get_effektiver_score(row)

        if score is not None:
            gruppen[wert].append(score)

        if row.get("auto_score") == "0":
            auto_nullen[wert] += 1

        bert = row.get("antwort_bert", "")
        rouge = row.get("antwort_rougeL", "")
        if bert not in ("", None):
            try:
                bert_scores[wert].append(float(bert))
            except ValueError:
                pass
        if rouge not in ("", None):
            try:
                rouge_scores[wert].append(float(rouge))
            except ValueError:
                pass

    if not gruppen:
        return

    print(f"\n{'─'*70}")
    print(f"📊 {titel}")
    print(f"{'─'*70}")
    print(f"{'Wert':<30} {'Score':>6} {'Std':>5} {'N':>4} {'Auto-0':>6} {'BERT':>6} {'ROUGE':>6}")
    print(f"{'─'*70}")

    sortiert = sorted(gruppen.items(), key=lambda x: -statistics.mean(x[1]))

    for wert, scores in sortiert:
        avg = statistics.mean(scores)
        std = statistics.stdev(scores) if len(scores) > 1 else 0.0
        n_auto = auto_nullen.get(wert, 0)
        avg_bert = statistics.mean(bert_scores[wert]) if bert_scores[wert] else 0.0
        avg_rouge = statistics.mean(rouge_scores[wert]) if rouge_scores[wert] else 0.0

        print(f"{str(wert):<30} {avg:>6.3f} {std:>5.3f} {len(scores):>4} "
              f"{n_auto:>6} {avg_bert:>6.3f} {avg_rouge:>6.3f}")


def analysiere_kategorie(daten: list):
    """Score pro Frage-Kategorie analysieren."""
    gruppen = defaultdict(list)
    auto_nullen = defaultdict(int)

    for row in daten:
        kat = row.get("kategorie", "?")
        score = get_effektiver_score(row)
        if score is not None:
            gruppen[kat].append(score)
        if row.get("auto_score") == "0":
            auto_nullen[kat] += 1

    if not gruppen:
        return

    print(f"\n{'─'*70}")
    print(f"📊 Score pro Kategorie")
    print(f"{'─'*70}")
    print(f"{'Kategorie':<20} {'Score':>6} {'Std':>5} {'N':>4} {'Auto-0':>6} {'Auto-0%':>8}")
    print(f"{'─'*70}")

    for kat, scores in sorted(gruppen.items(), key=lambda x: -statistics.mean(x[1])):
        avg = statistics.mean(scores)
        std = statistics.stdev(scores) if len(scores) > 1 else 0.0
        n_auto = auto_nullen.get(kat, 0)
        total = len(scores)
        auto_pct = n_auto / total * 100 if total > 0 else 0
        print(f"{kat:<20} {avg:>6.3f} {std:>5.3f} {len(scores):>4} "
              f"{n_auto:>6} {auto_pct:>7.1f}%")


def finde_verdaechtige_nullen(daten: list, bert_schwelle: float = 0.75,
                               rouge_schwelle: float = 0.25):
    """
    Findet Einträge mit score_manuell=0 aber hohen Metriken.
    Das sind potentielle Fehleingaben.

    Logik:
        Hoher BERT + hoher ROUGE-L + manuell 0 = verdächtig
        Weil: wenn Antwort semantisch UND lexikalisch nah an Referenz ist,
        war sie wahrscheinlich nicht falsch.

    Args:
        bert_schwelle:  BERT-Score ab dem es verdächtig ist
        rouge_schwelle: ROUGE-L Score ab dem es verdächtig ist
    """
    verdaechtig = []

    for row in daten:
        manuell = row.get("score_manuell", "")
        if manuell != "0":
            continue

        bert = row.get("antwort_bert", "")
        rouge = row.get("antwort_rougeL", "")

        try:
            bert_f = float(bert) if bert else 0.0
            rouge_f = float(rouge) if rouge else 0.0
        except ValueError:
            continue

        if bert_f >= bert_schwelle and rouge_f >= rouge_schwelle:
            verdaechtig.append({
                "run_id": row.get("run_id", "?"),
                "frage_id": row.get("frage_id", "?"),
                "kombination": (f"{row.get('llm_model')} | {row.get('embedding_model')} | "
                               f"c{row.get('chunk_size')} o{row.get('overlap')} | "
                               f"k{row.get('top_k')} | t{row.get('temperature')} | "
                               f"{row.get('system_prompt_name')}"),
                "antwort": row.get("generierte_antwort", "")[:120],
                "bert": bert_f,
                "rouge": rouge_f
            })

    if not verdaechtig:
        print(f"\n✅ Keine verdächtigen Nullen gefunden")
        return

    print(f"\n{'─'*70}")
    print(f"⚠️  VERDÄCHTIGE NULLEN ({len(verdaechtig)} Einträge)")
    print(f"   Kriterium: score_manuell=0 aber BERT≥{bert_schwelle} UND ROUGE≥{rouge_schwelle}")
    print(f"{'─'*70}")

    for v in verdaechtig:
        print(f"\nrun_id:  {v['run_id']}")
        print(f"Frage:   {v['frage_id']}")
        print(f"Kombi:   {v['kombination']}")
        print(f"BERT:    {v['bert']:.3f} | ROUGE-L: {v['rouge']:.3f}")
        print(f"Antwort: {v['antwort']}...")


def korrigiere_score(csv_path: str, run_id: str, neuer_score: int):
    """
    Korrigiert einen score_manuell Eintrag in der CSV.

    Args:
        csv_path:    Pfad zur CSV
        run_id:      run_id der zu korrigierenden Zeile
        neuer_score: Neuer Score (0, 1 oder 2)
    """
    path = Path(csv_path)
    daten = lade_csv(csv_path)

    gefunden = False
    for row in daten:
        if row.get("run_id") == run_id:
            alter_score = row.get("score_manuell", "")
            row["score_manuell"] = str(neuer_score)
            gefunden = True
            print(f"✅ run_id {run_id}: score_manuell {alter_score} → {neuer_score}")
            break

    if not gefunden:
        print(f"❌ run_id {run_id} nicht gefunden")
        return

    with open(path, "w", newline="", encoding="utf-8") as f:
        if daten:
            writer = csv.DictWriter(f, fieldnames=daten[0].keys())
            writer.writeheader()
            writer.writerows(daten)



def kreuztabelle(daten: list, zeile: str, spalte: str, titel: str):
    """
    Kreuztabelle: Score nach zwei Parametern gleichzeitig.
    Zeigt z.B. Embedding-Modell × Chunk-Size.

    Args:
        daten:   Liste von CSV-Zeilen
        zeile:   Parameter für Zeilen (z.B. "embedding_model")
        spalte:  Parameter für Spalten (z.B. "chunk_size")
        titel:   Anzeige-Titel
    """
    from collections import defaultdict
    import statistics

    # Alle Werte sammeln
    zellen = defaultdict(list)
    zeilen_werte = set()
    spalten_werte = set()

    for row in daten:
        z = row.get(zeile, "?")
        s = row.get(spalte, "?")
        score = get_effektiver_score(row)

        if score is not None:
            zellen[(z, s)].append(score)
            zeilen_werte.add(z)
            spalten_werte.add(s)

    if not zellen:
        return

    zeilen_werte = sorted(zeilen_werte)
    spalten_werte = sorted(spalten_werte, key=lambda x: float(x) if x.replace('.','').isdigit() else x)

    print(f"\n{'─'*70}")
    print(f"📊 KREUZTABELLE: {titel}")
    print(f"{'─'*70}")

    # Header
    header = f"{'':25}"
    for s in spalten_werte:
        header += f"{str(s):>8}"
    print(header)
    print(f"{'─'*70}")

    # Zeilen
    for z in zeilen_werte:
        row_str = f"{str(z)[:24]:<25}"
        for s in spalten_werte:
            werte = zellen.get((z, s), [])
            if werte:
                avg = statistics.mean(werte)
                row_str += f"{avg:>8.3f}"
            else:
                row_str += f"{'—':>8}"
        print(row_str)

    print(f"{'─'*70}")


def main():
    parser = argparse.ArgumentParser(description="SUSI Eval — CSV Analyse")
    parser.add_argument("--csv", required=True, help="Pfad zur CSV-Datei")
    parser.add_argument("--korrektur", action="store_true",
                        help="Verdächtige Nullen anzeigen")
    parser.add_argument("--fix", nargs=2, metavar=("RUN_ID", "SCORE"),
                        help="Score korrigieren: --fix run_id neuer_score")
    args = parser.parse_args()

    daten = lade_csv(args.csv)

    # Score-Verteilung
    alle_scores = [get_effektiver_score(r) for r in daten]
    scores_mit_wert = [s for s in alle_scores if s is not None]
    auto_nullen = sum(1 for r in daten if r.get("auto_score") == "0")

    print(f"\n{'='*70}")
    print(f"🔍 CSV ANALYSE — {Path(args.csv).name}")
    print(f"{'='*70}")
    print(f"   Gesamt Einträge    : {len(daten)}")
    print(f"   Mit Score          : {len(scores_mit_wert)}")
    print(f"   Auto-Score 0       : {auto_nullen} ({auto_nullen/len(daten)*100:.1f}%)")
    print(f"")
    print(f"   Score-Berechnung   : Durchschnitt aller Einträge (manuell + Auto-0)")
    print(f"   Skala              : 0.0 = alle falsch | 1.0 = alle teilweise | 2.0 = alle korrekt")
    print(f"")
    
    verteilung = {0: 0, 1: 0, 2: 0}
    for s in scores_mit_wert:
        if s in verteilung:
            verteilung[s] += 1
    print(f"   Score Verteilung   : 0={verteilung[0]} | 1={verteilung[1]} | 2={verteilung[2]}")
    
    gesamt_avg = statistics.mean(scores_mit_wert) if scores_mit_wert else 0
    print(f"   Gesamt-Score       : {gesamt_avg:.3f} von 2.0")
    print(f"   Als Prozent        : {gesamt_avg/2*100:.1f}% korrekt")
    print(f"{'='*70}")

    # Parameter-Analysen
    analysiere_parameter(daten, "embedding_model", "Embedding-Modell")
    analysiere_parameter(daten, "chunk_size", "Chunk-Size")
    analysiere_parameter(daten, "overlap", "Overlap")
    analysiere_parameter(daten, "top_k", "Top-K")
    analysiere_parameter(daten, "system_prompt_name", "System-Prompt")
    analysiere_parameter(daten, "llm_model", "LLM-Modell")
    analysiere_parameter(daten, "thinking", "Thinking-Modus")
    analysiere_parameter(daten, "temperature", "Temperature")
    analysiere_kategorie(daten)
    kreuztabelle(daten, "embedding_model", "chunk_size", "Embedding × Chunk-Size")
    kreuztabelle(daten, "embedding_model", "system_prompt_name", "Embedding × Prompt")
    kreuztabelle(daten, "llm_model", "chunk_size", "LLM × Chunk-Size")
    kreuztabelle(daten, "llm_model", "thinking", "LLM × Thinking")

    if args.korrektur:
        finde_verdaechtige_nullen(daten)

    if args.fix:
        run_id, score = args.fix
        korrigiere_score(args.csv, run_id, int(score))

    print(f"\n{'='*70}")
    print(f"Verdächtige Nullen prüfen:")
    print(f"  python tools/evaluation/analyse_csv.py --csv {args.csv} --korrektur")
    print(f"\nScore korrigieren:")
    print(f"  python tools/evaluation/analyse_csv.py --csv {args.csv} --fix RUN_ID 2")


if __name__ == "__main__":
    main()