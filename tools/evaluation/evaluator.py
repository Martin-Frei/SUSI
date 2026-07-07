"""
SUSI Evaluation — Evaluator
============================
Dieses Modul bewertet die Qualität von RAG-Antworten gegen Referenzantworten.

Wann verwenden:
    - Wird von grid_run.py automatisch importiert und verwendet
    - Kann standalone laufen um bestehende CSV auszuwerten:
      python tools/evaluation/evaluator.py --csv tools/evaluation/results/eval_xxx.csv

Was es tut:
    1. Auto-Score 0: erkennt Ausweichantworten automatisch ("nicht verfügbar" etc.)
    2. ROUGE-L: lexikalische Ähnlichkeit — erkennt falsche Namen/Fakten schärfer als BERTScore
    3. BERTScore: semantische Ähnlichkeit — erkennt sinnlose Antworten
    4. Chunk-level Scores: bewertet jeden Chunk gegen die Referenz
    5. Delta: antwort_bert - max_chunk_bert (Retrieval vs Generation Diagnose)
    6. Manuelle Bewertung: 0/1/2 Skala mit BERTScore-Diagnose-Anzeige
    7. Judge-Modell: automatische Bewertung via Claude API (optional, kostenpflichtig)
    8. CSV-Export: inkrementell, kann unterbrochen werden

Warum ROUGE-L + BERTScore kombiniert:
    BERTScore  → semantisch — "BERT-Modell" ≈ "nomic-Modell" (beide Embedding-Modelle)
    ROUGE-L    → lexikalisch — "BERT" ≠ "nomic-embed-text" → niedrigerer Score
    Kombination → BERTScore erkennt sinnlose Antworten, ROUGE-L erkennt falsche Fakten

Auto-Score Logik:
    Bestimmte Ausweichantworten werden automatisch mit 0 bewertet.
    Das spart manuelle Bewertungszeit bei eindeutig falschen Antworten.
    Liste der Ausweichantworten: AUSWEICH_ANTWORTEN (unten definiert)

Abhängigkeiten:
    pip install bert-score          für BERTScore
    pip install rouge-score         für ROUGE-L
    pip install anthropic           für Judge-Modell (optional)

Umgebungsvariablen:
    ANTHROPIC_API_KEY               nur für Judge-Modell nötig
"""

import os
import csv
csv.field_size_limit(10_000_000)
import json
import time
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, List


# ── Ausweichantworten — automatisch Score 0 ───────────────────────
# Antworten die eindeutig bedeuten dass SUSI nichts gefunden hat.
# Kleinschreibung, wird gegen lowercased Antwort geprüft.

AUSWEICH_ANTWORTEN = [
    "diese information ist nicht verfügbar",
    "diese information ist nicht verfuegbar",
    "dazu fehlt mir noch was in der susipedia",
    "ich habe keine information",
    "ich kann diese frage nicht beantworten",
    "keine information verfügbar",
    "nicht im kontext",
]


# ── Datenstrukturen ───────────────────────────────────────────────

@dataclass
class EvalResult:
    """
    Ein einzelnes Evaluierungs-Ergebnis — eine Zeile in der CSV.

    Parameter-Felder beschreiben die RAG-Konfiguration.
    Score-Felder beschreiben die Qualität der Antwort.
    Diagnose-Felder helfen bei der Fehlersuche.

    Wichtige Diagnose-Kombination:
        max_chunk_bert niedrig + antwort_bert niedrig  → Retrieval-Problem
        max_chunk_bert hoch   + antwort_bert niedrig  → Generation-Problem
        delta positiv + rougeL niedrig                → Halluzination (falsche Fakten)
        auto_score = 0                                → Ausweichantwort erkannt
    """
    run_id: str
    timestamp: str

    # RAG Parameter
    embedding_model: str
    chunk_size: int
    overlap: int
    separator: str
    top_k: int
    algorithm: str
    score_threshold: Optional[float]
    llm_model: str
    temperature: float
    system_prompt_name: str

    # Frage + Antwort
    frage_id: str
    kategorie: str
    frage: str
    referenzantwort: str
    generierte_antwort: str
    thinking: bool = False
    router_profil: str = "manuell"
    router_korrekt: Optional[bool] = None
    kontext_text: str = ""          # tatsächliche Chunks für manuelle Inspektion

    # Scores
    auto_score: Optional[int] = None        # 0 wenn Ausweichantwort erkannt
    score_manuell: Optional[int] = None     # 0/1/2 manuell
    score_judge: Optional[float] = None     # 0/1/2 via Judge-Modell

    # BERTScore — semantische Ähnlichkeit
    antwort_bert: Optional[float] = None        # Generation-Qualität
    max_chunk_bert: Optional[float] = None      # Retrieval-Qualität
    delta: Optional[float] = None               # positiv = verdächtig
    chunk_scores_bert: str = ""                 # alle Chunk-Scores kommagetrennt

    # ROUGE-L — lexikalische Ähnlichkeit (schärfer bei falschen Namen/Fakten)
    antwort_rougeL: Optional[float] = None      # ROUGE-L Antwort vs Referenz
    max_chunk_rougeL: Optional[float] = None    # bester Chunk ROUGE-L
    chunk_scores_rougeL: str = ""               # alle Chunk ROUGE-L Scores

    # Performance
    antwortzeit_sek: Optional[float] = None
    kontext_chunks: int = 0
    quelldateien: str = ""

    # Fehler
    fehler: str = ""


# ── Auto-Score ────────────────────────────────────────────────────

def pruefe_ausweichantwort(antwort: str) -> Optional[int]:
    """
    Prüft ob eine Antwort eine bekannte Ausweichantwort ist.

    Ausweichantworten bedeuten dass SUSI nichts gefunden hat oder
    den Prompt zu strikt interpretiert. Sie werden automatisch mit 0 bewertet.

    Args:
        antwort: Die generierte Antwort von SUSI

    Returns:
        0 wenn Ausweichantwort erkannt
        None wenn keine Ausweichantwort — normale Bewertung nötig
    """
    antwort_lower = antwort.lower().strip()
    for ausweich in AUSWEICH_ANTWORTEN:
        if ausweich in antwort_lower:
            return 0
    return None


# ── CSV-Writer ────────────────────────────────────────────────────

class CSVWriter:
    """
    Schreibt EvalResult-Objekte inkrementell in eine CSV-Datei.

    Inkrementell: jede Zeile sofort auf Disk — Lauf kann jederzeit
    unterbrochen werden ohne Datenverlust.

    Verwendung:
        writer = CSVWriter("tools/evaluation/results/eval_20260524_1423_smoke.csv")
        writer.write(result)
        writer.close()  # immer in finally-Block!
    """

    FELDER = [
        "run_id", "timestamp",
        "embedding_model", "chunk_size", "overlap", "separator",
        "top_k", "algorithm", "score_threshold",
        "llm_model", "thinking", "temperature", "system_prompt_name", "router_profil", "router_korrekt",
        "frage_id", "kategorie", "frage",
        "referenzantwort", "generierte_antwort", "kontext_text",
        "auto_score", "score_manuell", "score_judge",
        "antwort_bert", "max_chunk_bert", "delta", "chunk_scores_bert",
        "antwort_rougeL", "max_chunk_rougeL", "chunk_scores_rougeL",
        "antwortzeit_sek", "kontext_chunks", "quelldateien",
        "fehler"
    ]

    def __init__(self, output_path: str):
        """
        Args:
            output_path: Vollständiger Pfad zur CSV-Datei.
                         Verzeichnis wird automatisch erstellt.
                         Falls Datei existiert wird angehängt (Fortsetzung).
        """
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    def _init_file(self):
        """Header schreiben falls Datei neu, sonst anhängen."""
        if not self._initialized:
            write_header = not self.output_path.exists()
            self._file = open(self.output_path, "a", newline="", encoding="utf-8")
            self._writer = csv.DictWriter(self._file, fieldnames=self.FELDER)
            if write_header:
                self._writer.writeheader()
                self._file.flush()
            self._initialized = True

    def write(self, result: EvalResult):
        """
        Einen EvalResult sofort in die CSV schreiben und flushen.

        Args:
            result: Das zu schreibende EvalResult-Objekt
        """
        self._init_file()
        row = asdict(result)
        row_filtered = {k: row.get(k, "") for k in self.FELDER}
        self._writer.writerow(row_filtered)
        self._file.flush()

    def close(self):
        """Datei schließen. Immer in einem finally-Block aufrufen."""
        if self._initialized:
            self._file.close()


# ── ROUGE-L ───────────────────────────────────────────────────────

def berechne_rouge_scores(
    antwort: str,
    referenz: str,
    chunks: List[str]
) -> dict:
    """
    Berechnet ROUGE-L Scores für Antwort und alle Chunks gegen die Referenz.

    ROUGE-L misst die längste gemeinsame Teilfolge (Longest Common Subsequence).
    Vorteil gegenüber BERTScore: erkennt falsche Namen und Fakten besser.

    Beispiel warum ROUGE-L schärfer ist:
        Referenz: "nomic-embed-text als Embedding-Modell"
        Antwort A: "BERT als Embedding-Modell"
            BERTScore: 0.87  (semantisch ähnlich — beide Embedding-Modelle)
            ROUGE-L:   0.40  (lexikalisch — "BERT" ≠ "nomic-embed-text")
        Antwort B: "Diese Information ist nicht verfügbar"
            BERTScore: 0.62
            ROUGE-L:   0.00  (kein gemeinsames Wort mit Referenz)

    Args:
        antwort:    Die von SUSI generierte Antwort
        referenz:   Die manuell definierte Referenzantwort
        chunks:     Liste der Chunk-Texte die SUSI bekommen hat

    Returns:
        dict mit antwort_rougeL, max_chunk_rougeL, chunk_scores_rougeL
        Bei Fehler: alle Werte None, fehler-Key mit Fehlermeldung
    """
    try:
        from rouge_score import rouge_scorer

        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)

        if not antwort or not referenz:
            return {
                "antwort_rougeL": None,
                "max_chunk_rougeL": None,
                "chunk_scores_rougeL": "",
                "fehler": "Antwort oder Referenz leer"
            }

        # Antwort vs Referenz
        score_antwort = scorer.score(referenz, antwort)
        antwort_rougeL = round(score_antwort["rougeL"].fmeasure, 4)

        # Jeden Chunk vs Referenz
        chunk_scores = []
        for chunk in chunks:
            s = scorer.score(referenz, chunk)
            chunk_scores.append(round(s["rougeL"].fmeasure, 4))

        max_chunk_rougeL = max(chunk_scores) if chunk_scores else None

        return {
            "antwort_rougeL": antwort_rougeL,
            "max_chunk_rougeL": max_chunk_rougeL,
            "chunk_scores_rougeL": ",".join(str(s) for s in chunk_scores),
            "fehler": ""
        }

    except ImportError:
        return {
            "antwort_rougeL": None,
            "max_chunk_rougeL": None,
            "chunk_scores_rougeL": "",
            "fehler": "rouge-score nicht installiert: pip install rouge-score"
        }
    except Exception as e:
        return {
            "antwort_rougeL": None,
            "max_chunk_rougeL": None,
            "chunk_scores_rougeL": "",
            "fehler": f"ROUGE-L Fehler: {e}"
        }


# ── BERTScore ─────────────────────────────────────────────────────

def berechne_bert_scores(
    antwort: str,
    referenz: str,
    chunks: List[str],
    lang: str = "de"
) -> dict:
    """
    Berechnet BERTScores für Antwort und alle Chunks gegen die Referenz.

    BERTScore misst semantische Ähnlichkeit (0.0-1.0).
    Schwäche: erkennt falsche Namen schlecht (beide "Embedding-Modell" → hoher Score).
    Stärke: erkennt komplett sinnlose Antworten ("Kurzzeitgedächtnis" → niedriger Score).

    Delta-Interpretation:
        delta negativ  → Chunk hatte Info, LLM hat sie verloren (Generation-Problem)
        delta positiv  → Chunk hatte Info nicht, LLM antwortete trotzdem (verdächtig!)
        delta ≈ 0      → LLM hat besten Chunk gut genutzt

    Bei top_k=8: 8 Chunk-Scores + 1 Antwort-Score = 9 BERTScores pro Lauf.

    Args:
        antwort:    Die von SUSI generierte Antwort
        referenz:   Die manuell definierte Referenzantwort
        chunks:     Liste der Chunk-Texte die SUSI bekommen hat
        lang:       Sprache für BERTScore ("de" für Deutsch)

    Returns:
        dict mit antwort_bert, max_chunk_bert, delta, chunk_scores_bert
        Bei Fehler: alle Werte None
    """
    try:
        from bert_score import score as bert_score_fn

        if not antwort or not referenz:
            return {
                "antwort_bert": None,
                "max_chunk_bert": None,
                "delta": None,
                "chunk_scores_bert": "",
                "fehler": "Antwort oder Referenz leer"
            }

        # Antwort vs Referenz
        _, _, f1_antwort = bert_score_fn(
            [antwort], [referenz], lang=lang, verbose=False
        )
        antwort_bert = round(f1_antwort[0].item(), 4)

        # Jeden Chunk vs Referenz
        chunk_scores = []
        if chunks:
            referenzen = [referenz] * len(chunks)
            _, _, f1_chunks = bert_score_fn(
                chunks, referenzen, lang=lang, verbose=False
            )
            chunk_scores = [round(s.item(), 4) for s in f1_chunks]

        max_chunk_bert = max(chunk_scores) if chunk_scores else None
        delta = round(antwort_bert - max_chunk_bert, 4) if max_chunk_bert is not None else None

        return {
            "antwort_bert": antwort_bert,
            "max_chunk_bert": max_chunk_bert,
            "delta": delta,
            "chunk_scores_bert": ",".join(str(s) for s in chunk_scores),
            "fehler": ""
        }

    except ImportError:
        return {
            "antwort_bert": None,
            "max_chunk_bert": None,
            "delta": None,
            "chunk_scores_bert": "",
            "fehler": "bert-score nicht installiert: pip install bert-score"
        }
    except Exception as e:
        return {
            "antwort_bert": None,
            "max_chunk_bert": None,
            "delta": None,
            "chunk_scores_bert": "",
            "fehler": f"BERTScore Fehler: {e}"
        }


# ── Manuelle Bewertung ────────────────────────────────────────────

def score_manuell(frage: str, referenz: str, antwort: str,
                  bert_info: dict = None,
                  rouge_info: dict = None) -> int:
    """
    Interaktive manuelle Bewertung einer SUSI-Antwort.

    Zeigt Frage, Referenz, Antwort und Diagnose-Metriken.
    Wartet auf Tasteneingabe: 0, 1, 2, s (skip) oder q (quit).

    Diagnose-Anzeige:
        BERTScore + ROUGE-L + Delta werden angezeigt
        Automatische Einschätzung: Generation-Problem / Verdächtig / Unauffällig

    Bewertungsskala:
        0 = Falsch — inhaltlich falsch oder halluziniert
        1 = Teilweise — Kernaussage stimmt, aber unvollständig
        2 = Korrekt — vollständig und faktisch richtig

    Args:
        frage:      Der Fragetext
        referenz:   Die Referenzantwort
        antwort:    Die von SUSI generierte Antwort
        bert_info:  BERTScore-Ergebnisse für Diagnose-Anzeige
        rouge_info: ROUGE-L Ergebnisse für Diagnose-Anzeige

    Returns:
        int: 0, 1 oder 2
        -1 wenn übersprungen (s)

    Raises:
        KeyboardInterrupt wenn q gedrückt wird
    """
    print("\n" + "="*60)
    print(f"❓ FRAGE:\n{frage}\n")
    print(f"✅ REFERENZ:\n{referenz}\n")
    print(f"🤖 SUSI:\n{antwort}\n")

    # Diagnose anzeigen
    if bert_info and bert_info.get("antwort_bert") is not None:
        delta = bert_info.get("delta")
        diagnose = ""
        if delta is not None:
            if delta < -0.1:
                diagnose = "⚠️  Generation-Problem (Chunk hatte Info, LLM hat sie verloren)"
            elif delta > 0.1:
                diagnose = "🔴 Verdächtig — Halluzination oder Modell-Wissen?"
            else:
                diagnose = "✅ Unauffällig"

        rouge_str = ""
        if rouge_info and rouge_info.get("antwort_rougeL") is not None:
            rouge_str = f" | ROUGE-L: {rouge_info['antwort_rougeL']:.3f}"

        print(f"📊 BERT: {bert_info['antwort_bert']:.3f} | "
              f"MaxChunk: {bert_info['max_chunk_bert']:.3f} | "
              f"Delta: {delta:+.3f}{rouge_str}")
        if diagnose:
            print(f"   {diagnose}")

    print("─"*60)
    print("Bewertung: 0 = Falsch | 1 = Teilweise | 2 = Korrekt")
    print("           s = Überspringen | q = Beenden")

    while True:
        eingabe = input("Score: ").strip().lower()
        if eingabe in ("0", "1", "2"):
            return int(eingabe)
        elif eingabe == "s":
            return -1
        elif eingabe == "q":
            raise KeyboardInterrupt("Manuelles Beenden durch Benutzer")
        else:
            print("Bitte 0, 1, 2, s oder q eingeben.")


# ── Judge-Modell ──────────────────────────────────────────────────

def score_mit_judge(frage: str, referenz: str, antwort: str,
                    judge_model: str = "claude-sonnet-4-20250514",
                    api_key: str = None) -> Optional[float]:
    """
    Automatische Bewertung durch ein Judge-Modell via Claude API.

    Gibt Score 0.0, 1.0 oder 2.0 zurück (gleiche Skala wie manuell).
    Vorteil: schnell bei vielen Kombinationen.
    Nachteil: kostenpflichtig, möglicher Bias.

    Voraussetzung: ANTHROPIC_API_KEY als Umgebungsvariable.

    Args:
        frage:          Der Fragetext
        referenz:       Die Referenzantwort
        antwort:        Die zu bewertende SUSI-Antwort
        judge_model:    Claude-Modell für die Bewertung
        api_key:        API-Key (falls nicht als Umgebungsvariable)

    Returns:
        float: 0.0, 1.0 oder 2.0
        None bei Fehler oder fehlendem API-Key
    """
    try:
        import anthropic

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            print("  ⚠️  ANTHROPIC_API_KEY nicht gesetzt — Judge übersprungen")
            return None

        client = anthropic.Anthropic(api_key=key)

        judge_prompt = f"""Du bewertest die Qualität einer KI-Antwort.

FRAGE: {frage}

REFERENZANTWORT (korrekte Antwort):
{referenz}

GENERIERTE ANTWORT (zu bewerten):
{antwort}

Bewertungsskala:
0 = Falsch oder halluziniert
1 = Teilweise korrekt
2 = Korrekt und vollständig

Antworte NUR mit einer Zahl: 0, 1 oder 2."""

        message = client.messages.create(
            model=judge_model,
            max_tokens=10,
            messages=[{"role": "user", "content": judge_prompt}]
        )

        score = float(message.content[0].text.strip())
        return score if score in (0.0, 1.0, 2.0) else None

    except Exception as e:
        print(f"  ⚠️  Judge-Fehler: {e}")
        return None


# ── Ergebnis-Analyse ──────────────────────────────────────────────

def lade_ergebnisse(csv_path: str) -> list:
    """
    CSV laden und als Liste von Dicts zurückgeben.

    Args:
        csv_path: Pfad zur CSV-Datei

    Returns:
        Liste von Dicts, leer wenn Datei nicht existiert
    """
    path = Path(csv_path)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def beste_kombination(ergebnisse: list, score_feld: str = "score_manuell") -> list:
    """
    Findet die besten Parameter-Kombinationen nach Durchschnitt-Score.

    Sortiert nach avg_score DESC, std_score ASC.
    Stabilität (niedriger Std) ist wichtiger als Spitzenwert.

    Args:
        ergebnisse:  Liste von Dicts aus lade_ergebnisse()
        score_feld:  "score_manuell", "score_judge" oder "auto_score"

    Returns:
        Liste von Dicts sortiert nach Qualität
    """
    from collections import defaultdict
    import statistics

    gruppen = defaultdict(list)

    for row in ergebnisse:
        score = row.get(score_feld)
        if score in (None, "", "-1"):
            continue
        try:
            score = float(score)
        except ValueError:
            continue

        key = (
            row["embedding_model"], row["chunk_size"], row["overlap"],
            row["top_k"], row["algorithm"],
            row["llm_model"], row["temperature"], row["system_prompt_name"]
        )
        gruppen[key].append(score)

    if not gruppen:
        return []

    result = []
    for key, scores in gruppen.items():
        avg = statistics.mean(scores)
        std = statistics.stdev(scores) if len(scores) > 1 else 0.0
        result.append({
            "embedding_model": key[0], "chunk_size": key[1], "overlap": key[2],
            "top_k": key[3], "algorithm": key[4],
            "llm_model": key[5], "temperature": key[6], "system_prompt_name": key[7],
            "n_fragen": len(scores),
            "avg_score": round(avg, 3),
            "std_score": round(std, 3),
            "min_score": min(scores),
            "max_score": max(scores)
        })

    result.sort(key=lambda x: (-x["avg_score"], x["std_score"]))
    return result


def drucke_zusammenfassung(csv_path: str, top_n: int = 5):
    """
    Zeigt Top-N beste Kombinationen + Score-Statistiken.

    Args:
        csv_path:  Pfad zur CSV-Datei
        top_n:     Anzahl der anzuzeigenden Kombinationen
    """
    ergebnisse = lade_ergebnisse(csv_path)

    if not ergebnisse:
        print("Keine Ergebnisse gefunden.")
        return

    print(f"\n{'='*70}")
    print(f"📊 EVALUATION ZUSAMMENFASSUNG — {Path(csv_path).name}")
    print(f"   Gesamt Einträge : {len(ergebnisse)}")

    # Auto-Score Statistik
    auto_nullen = sum(1 for r in ergebnisse if r.get("auto_score") == "0")
    if auto_nullen:
        print(f"   Auto-Score 0    : {auto_nullen} Ausweichantworten erkannt")

    # Top-N Kombinationen
    beste = beste_kombination(ergebnisse, "score_manuell")
    if beste:
        print(f"\n🏆 TOP {top_n} KOMBINATIONEN (manueller Score):")
        print(f"{'Rang':<4} {'Score':>6} {'Std':>5} {'N':>3}  Kombination")
        print("─"*70)
        for i, b in enumerate(beste[:top_n], 1):
            kombi = (f"{b['llm_model']} | {b['embedding_model']} | "
                    f"c{b['chunk_size']} o{b['overlap']} | "
                    f"k{b['top_k']} {b['algorithm']} | "
                    f"t{b['temperature']} | {b['system_prompt_name']}")
            print(f"#{i:<3} {b['avg_score']:>6.2f} {b['std_score']:>5.2f} {b['n_fragen']:>3}  {kombi}")

    # BERTScore Statistik
    bert_werte = [float(r["antwort_bert"]) for r in ergebnisse
                  if r.get("antwort_bert") not in (None, "")]
    rouge_werte = [float(r["antwort_rougeL"]) for r in ergebnisse
                   if r.get("antwort_rougeL") not in (None, "")]

    if bert_werte:
        import statistics
        print(f"\n📐 BERT (semantisch) — Ø {statistics.mean(bert_werte):.3f} "
              f"| Min {min(bert_werte):.3f} | Max {max(bert_werte):.3f}")
    if rouge_werte:
        import statistics
        print(f"📐 ROUGE-L (lexikalisch) — Ø {statistics.mean(rouge_werte):.3f} "
              f"| Min {min(rouge_werte):.3f} | Max {max(rouge_werte):.3f}")

    print(f"{'='*70}")


# ── Standalone ────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Standalone-Aufruf für Auswertung einer bestehenden CSV.

    Beispiel:
        python tools/evaluation/evaluator.py --csv tools/evaluation/results/eval_xxx.csv
        python tools/evaluation/evaluator.py --csv tools/evaluation/results/eval_xxx.csv --top 10
    """
    import argparse

    parser = argparse.ArgumentParser(description="SUSI Eval — Auswertung")
    parser.add_argument("--csv", required=True, help="Pfad zur CSV-Datei")
    parser.add_argument("--top", type=int, default=10, help="Top-N anzeigen")
    args = parser.parse_args()

    drucke_zusammenfassung(args.csv, top_n=args.top)