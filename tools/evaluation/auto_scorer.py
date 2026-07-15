"""
SUSI Evaluation — Automatischer Scorer
========================================
Berechnet automatisch einen Score (0-5) aus den Metriken.
Basiert auf empirischen Schwellenwerten aus dem ersten Grid-Lauf (768 Läufe).

Skala:
    0  →  Ausweichantwort ("nicht verfügbar") — Prompt zu strikt oder Retrieval leer
    1  →  Halluzination — LLM erfindet komplett, kein Chunk, kein Training
    2  →  Training korrekt — richtiger Chunk nicht gefunden, LLM antwortet aus Training
    3  →  RAG korrekt ✅ — richtiger Chunk gefunden, richtige Antwort
    4  →  RAG falsch — Generation-Problem — Chunk gut aber LLM macht Fehler
    5  →  RAG falsch — falscher Chunk — Retrieval in falsche Kategorie
    6  →  ValueCheck-Konflikt — Wertefehler bei hohen BERT/ROUGE-Metriken
         → Grauzone: RAGAS entscheidet (typisch: verschiedene korrekte Zahlen
         für denselben Sachverhalt, z.B. "Faktor 18" vs "52 Prozentpunkte")

Schwellenwerte (aus 768 echten Einträgen berechnet):
    ROUGE-L < 0.05                          →  0 oder 1
    ROUGE-L > 0.25 + BERT > 0.75           →  3 (sicher)
    max_chunk_rougeL < 0.10 + ROUGE-L < 0.05 → 5 (falscher Chunk)
    max_chunk_bert > 0.70 + ROUGE-L < 0.10  → 4 (Generation-Problem)
    Alles andere                            →  Grauzone → manuell

Automatisierungsgrad aus erstem Lauf: 71.6%
Genauigkeit automatischer Entscheidungen: ~88%

NEU (06.07.2026) — ValueCheck:
    Deterministische Werte-Prüfung (Zahlen, Daten, Wochentage) läuft
    VOR dem ROUGE/BERT-Entscheidungsbaum, wenn eine Referenz übergeben
    wird. Schließt die Lücke dass Similarity-Metriken numerisch falsche,
    aber fließend formulierte Antworten als korrekt bewerten
    (Befund eval_20260630_1218: 10/10 auto_score=3, real 5/10 falsch).
    Sicherer Wertefehler → Score 1. Unsichere Fälle → Grauzone.

Aufruf standalone:
    python tools/evaluation/auto_scorer.py --csv tools/evaluation/results/eval_xxx.csv
"""

from typing import Optional

try:
    from valuecheck import pruefe_werte as _valuecheck_pruefe
    VALUECHECK_VERFUEGBAR = True
except ImportError:
    VALUECHECK_VERFUEGBAR = False


# ── Konstanten ────────────────────────────────────────────────────
MAX_SCORE = 6
KORREKT_THRESHOLD = 2   # Score >= 2 gilt als korrekt

# Zentrales Mapping Diagnostic-Skala (0-6) → Quality-Skala (0-2/None).
# Bisher dreifach dupliziert in grid_run.py, ragas_scorer.py und
# analyse_csv.py — hier ist ab jetzt die Single Source of Truth.
# 0=Ausweich→0, 1=Halluzination→0, 2=Training→1,
# 3=RAG korrekt→2, 4=Generation→0, 5=Falscher Chunk→0,
# 6=ValueCheck-Konflikt→None (Grauzone, RAGAS entscheidet)
DIAG_ZU_QUALITAET = {0: 0, 1: 0, 2: 1, 3: 2, 4: 0, 5: 0, 6: None}

# Rollout-Schalter für ValueCheck:
#   True  = sicherer Wertefehler wird hart Score 1 (Zielzustand)
#   False = Wertefehler geht als Grauzone an RAGAS/Haiku (Einführungsphase,
#           solange Referenzantworten noch Meta-Text/Störwerte enthalten)
# Hintergrund: im Rewriter-Testset enthalten Referenzen Sätze wie
# "Diese Frage testet ob ..." inkl. Hardware-Nummern (RTX 4070) — solche
# Werte gehören nicht zur erwarteten Antwort und können korrekte Antworten
# fälschlich hart durchfallen lassen (Beispiel rwfix_10).
VALUECHECK_HART = True


# ── Schwellenwerte (aus echten Daten) ─────────────────────────────

SCHWELLEN = {
    "ausweich_rouge": 0.05,
    "korrekt_rouge": 0.15,
    "korrekt_bert": 0.65,
    "falscher_chunk_rouge": 0.10,
    "generation_chunk_bert": 0.70,
    "generation_antwort_rouge": 0.10,
    "grauzone_rouge_min": 0.05,
    "grauzone_rouge_max": 0.25,
}

# Bekannte Ausweich-Phrasen — erweitert nach qwen/llama Tests (Juni 2026)
AUSWEICH_PHRASEN = [
    # Original
    "diese information ist nicht verfügbar",
    "diese information ist nicht verfuegbar",
    "dazu fehlt mir noch was in der susipedia",
    "ich habe keine information dazu",
    "ich kann diese frage nicht beantworten",
    "keine information verfügbar",
    # Neu — qwen2.5-coder Formulierungen
    "ich habe keine informationen über",
    "ich habe keine informationen zu",
    "ich kann nicht antworten, da ich keine informationen",
    "leider habe ich keine informationen",
    "ich bin nicht in der lage, diese frage zu beantworten",
    "es tut mir leid, aber ich kann diese frage nicht",
    "ich habe keine direkten informationen",
    "diese information steht mir nicht zur verfügung",
    # Neu — llama3.1 Formulierungen
    "ich muss darauf hinweisen, dass ich keine informationen",
    "ich habe nach informationen gesucht",
    "leider habe ich keine direkten informationen",
    "es ist nicht möglich, genaue informationen",
    # Englische Ausweicher (Mehrsprachigkeit)
    "i don't have information about",
    "i cannot answer this question",
    "i have no information about",
    "this information is not available",
]


# ── Kernfunktion ──────────────────────────────────────────────────

def berechne_auto_score(
    antwort: str,
    antwort_bert: Optional[float],
    max_chunk_bert: Optional[float],
    delta: Optional[float],
    antwort_rougeL: Optional[float],
    max_chunk_rougeL: Optional[float],
    auto_score_ausweich: Optional[int] = None,
    referenz: Optional[str] = None
) -> dict:
    """
    Berechnet automatisch einen Score (0-5) aus den Metriken.

    referenz: Optional. Wenn übergeben, läuft ValueCheck (deterministischer
    Zahlen/Daten/Wochentags-Vergleich) VOR dem Metrik-Baum. Ohne Referenz
    verhält sich die Funktion exakt wie bisher (rückwärtskompatibel).
    """

    # Schritt 1 — Ausweichantwort via Auto-Score Flag
    if auto_score_ausweich == 0:
        return {
            "score": 0,
            "konfidenz": "hoch",
            "grund": "Ausweichantwort erkannt (Auto-Score)",
            "manuell": False
        }

    # Ausweich-Phrasen prüfen (Teilstring-Matching am Anfang)
    if antwort:
        antwort_lower = antwort.lower().strip()
        for phrase in AUSWEICH_PHRASEN:
            if phrase == antwort_lower or antwort_lower.startswith(phrase):
                return {
                    "score": 0,
                    "konfidenz": "hoch",
                    "grund": f"Ausweichantwort erkannt: '{phrase[:50]}'",
                    "manuell": False
                }

    # Schritt 1b — ValueCheck: deterministischer Werte-Vergleich
    # Läuft nur wenn Referenz übergeben wurde und valuecheck.py vorhanden ist.
    # BERT/ROUGE können numerisch falsche, fließend formulierte Antworten
    # nicht erkennen — ValueCheck vergleicht Zahlen, Daten und Wochentage
    # direkt Wert gegen Wert.
    #
    # KONFLIKT-ERKENNUNG (15.07.2026):
    # Wenn ValueCheck "falsch" sagt aber BERT/ROUGE hohe Werte zeigen,
    # liegt vermutlich kein echter Fehler vor sondern ein alternativer
    # korrekter Ausdruck (z.B. "Faktor 18" vs "52 Prozentpunkte").
    # In diesem Fall → Diagnostic 6 (Grauzone, RAGAS entscheidet)
    # statt hart Diagnostic 1 (Halluzination).
    if referenz and antwort and VALUECHECK_VERFUEGBAR:
        vc = _valuecheck_pruefe(referenz, antwort)
        if vc["status"] == "falsch":
            # Prüfen ob die Similarity-Metriken der Diagnose widersprechen
            _rouge = antwort_rougeL or 0
            _bert = antwort_bert or 0
            metriken_hoch = (_rouge > SCHWELLEN["korrekt_rouge"]
                            and _bert > SCHWELLEN["korrekt_bert"])

            if metriken_hoch:
                # Konflikt: ValueCheck sagt falsch, Metriken sagen korrekt
                # → Grauzone (Score 6), RAGAS entscheidet
                return {
                    "score": 6,
                    "konfidenz": "grauzone",
                    "grund": (f"ValueCheck-Konflikt: {vc['grund']} "
                              f"(aber BERT={_bert:.3f}, ROUGE={_rouge:.3f})"),
                    "manuell": True
                }

            if VALUECHECK_HART:
                return {
                    "score": 1,
                    "konfidenz": "hoch",
                    "grund": f"ValueCheck: {vc['grund']}",
                    "manuell": False
                }
            return {
                "score": None,
                "konfidenz": "grauzone",
                "grund": f"ValueCheck (weich): {vc['grund']}",
                "manuell": True
            }
        if vc["status"] == "grauzone":
            return {
                "score": None,
                "konfidenz": "grauzone",
                "grund": f"ValueCheck Grauzone: {vc['grund']}",
                "manuell": True
            }
        # "korrekt" oder "inaktiv" → ValueCheck gibt frei,
        # bestehender ROUGE/BERT-Baum entscheidet wie bisher.

    rouge = antwort_rougeL
    bert = antwort_bert
    chunk_rouge = max_chunk_rougeL
    chunk_bert = max_chunk_bert

    if rouge is None or bert is None:
        return {
            "score": None,
            "konfidenz": "grauzone",
            "grund": "Metriken fehlen",
            "manuell": True
        }

    # Schritt 2 — ROUGE-L sehr niedrig
    if rouge < SCHWELLEN["ausweich_rouge"]:

        if chunk_rouge is not None and chunk_rouge < SCHWELLEN["falscher_chunk_rouge"]:
            return {
                "score": 5,
                "konfidenz": "mittel",
                "grund": f"Falscher Chunk — ROUGE-L={rouge:.3f}, ChunkROUGE={chunk_rouge:.3f}",
                "manuell": False
            }

        if chunk_bert is not None and chunk_bert > SCHWELLEN["generation_chunk_bert"]:
            return {
                "score": 4,
                "konfidenz": "mittel",
                "grund": f"Generation-Problem — ChunkBERT={chunk_bert:.3f}, ROUGE-L={rouge:.3f}",
                "manuell": False
            }

        return {
            "score": 1,
            "konfidenz": "mittel",
            "grund": f"Halluzination — ROUGE-L={rouge:.3f}, BERT={bert:.3f}",
            "manuell": False
        }

    # Schritt 3 — ROUGE-L hoch + BERT hoch → Score 3
    if rouge > SCHWELLEN["korrekt_rouge"] and bert > SCHWELLEN["korrekt_bert"]:
        return {
            "score": 3,
            "konfidenz": "hoch",
            "grund": f"RAG korrekt — ROUGE-L={rouge:.3f}, BERT={bert:.3f}",
            "manuell": False
        }

    # Schritt 4 — ROUGE-L hoch + Delta positiv → Score 2
    if rouge > SCHWELLEN["korrekt_rouge"] and delta is not None and delta > 0.10:
        return {
            "score": 2,
            "konfidenz": "mittel",
            "grund": f"Training korrekt — ROUGE-L={rouge:.3f}, Delta={delta:.3f}",
            "manuell": False
        }

    # Schritt 5 — Grauzone
    return {
        "score": None,
        "konfidenz": "grauzone",
        "grund": f"Grauzone — ROUGE-L={rouge:.3f}, BERT={bert:.3f}, Delta={f'{delta:.3f}' if delta is not None else 'N/A'}",
        "manuell": True
    }


# ── Qualitätsscore (0/2 nur bei hoher Konfidenz) ─────────────────
#
# Schreibt nur in score_manuell — und nur wenn sicher:
#   Score 0 → Ausweichantwort erkannt (100% sicher)
#   Score 2 → ROUGE-L + BERT beide hoch (hohe Konfidenz)
#   None    → Grauzone → manuell bewerten
#
# Score 1 wird NIE automatisch gesetzt — zu unsicher.
# Diagnosescore (0-5) läuft separat in berechne_auto_score().

def berechne_qualitaets_score(
    antwort: str,
    antwort_bert: Optional[float],
    antwort_rougeL: Optional[float],
    auto_score_ausweich: Optional[int] = None
) -> Optional[int]:
    """
    Berechnet den Qualitätsscore (0/2/None) für score_manuell.

    Fragt: "Ist die Antwort für den User brauchbar?"
    Nur bei hoher Konfidenz automatisch — sonst None (manuell nötig).

    Skala:
        0    → Ausweichantwort erkannt — sicher falsch
        2    → ROUGE-L > 0.25 + BERT > 0.75 — sicher korrekt
        None → Grauzone — manuell bewerten

    Score 1 (teilweise) wird nie automatisch gesetzt.
    Wird nie mit auto_score (0-5) vermischt.

    Args:
        antwort:             Generierte Antwort
        antwort_bert:        BERTScore Antwort vs Referenz
        antwort_rougeL:      ROUGE-L Antwort vs Referenz
        auto_score_ausweich: Wenn 0 → Ausweichantwort bereits erkannt

    Returns:
        0, 2 oder None
    """
    # Ausweichantwort → sicher Score 0
    if auto_score_ausweich == 0:
        return 0

    if antwort:
        antwort_lower = antwort.lower().strip()
        for phrase in AUSWEICH_PHRASEN:
            if phrase == antwort_lower or antwort_lower.startswith(phrase):
                return 0

    # Metriken fehlen → Grauzone
    if antwort_bert is None or antwort_rougeL is None:
        return None

    # Beide Metriken hoch → sicher Score 2
    if antwort_rougeL > 0.25 and antwort_bert > 0.75:
        return 2

    # Alles andere → manuell
    return None


# ── Konsolen-Anzeige ──────────────────────────────────────────────

def zeige_auto_score(result: dict, frage: str, referenz: str, antwort: str,
                     bert_info: dict | None = None, rouge_info: dict | None = None) -> Optional[int]:
    SCORE_LABELS = {
        0: "Ausweichantwort",
        1: "Halluzination",
        2: "Training korrekt",
        3: "RAG korrekt ✅",
        4: "RAG falsch — Generation",
        5: "RAG falsch — falscher Chunk",
        6: "ValueCheck-Konflikt → Grauzone"
    }

    if not result["manuell"] and result["score"] is not None:
        label = SCORE_LABELS.get(result["score"], "?")
        symbol = "✅" if result["konfidenz"] == "hoch" else "🔶"
        print(f"  {symbol} Auto-Score {result['score']} ({label}) — {result['grund']}")
        return result["score"]

    print(f"\n{'='*60}")
    print(f"❓ FRAGE:\n{frage}\n")
    print(f"✅ REFERENZ:\n{referenz}\n")
    print(f"🤖 SUSI:\n{antwort}\n")

    if bert_info and bert_info.get("antwort_bert") is not None:
        rouge_str = ""
        if rouge_info and rouge_info.get("antwort_rougeL") is not None:
            rouge_str = f" | ROUGE-L: {rouge_info['antwort_rougeL']:.3f} | ChunkROUGE: {rouge_info.get('max_chunk_rougeL', 0):.3f}"
        print(f"📊 BERT: {bert_info['antwort_bert']:.3f} | "
              f"MaxChunk: {bert_info['max_chunk_bert']:.3f} | "
              f"Delta: {bert_info['delta']:+.3f}{rouge_str}")

    print(f"🔶 Grauzone — {result['grund']}")
    print(f"   Diagnose (auto_score): {result['score']} — wird automatisch gespeichert")
    print(f"─"*60)
    print(f"Qualitätsbewertung für score_manuell:")
    print(f"  0 = Falsch/nutzlos | 1 = Teilweise | 2 = Korrekt")
    print(f"  s = Überspringen   | q = Beenden")
    print(f"  (Diagnosescore 0-5 wird separat in auto_score gespeichert)")

    while True:
        eingabe = input("Score (0/1/2): ").strip().lower()
        if eingabe in ("0", "1", "2"):
            return int(eingabe)
        elif eingabe in ("3", "4", "5"):
            print("⚠️  Diagnosescores (3-5) gehören in auto_score, nicht hier.")
            print("   Bitte 0=Falsch, 1=Teilweise, 2=Korrekt eingeben.")
        elif eingabe == "s":
            return -1
        elif eingabe == "q":
            raise KeyboardInterrupt("Beenden")
        else:
            print("Bitte 0, 1, 2, s oder q eingeben.")


# ── Batch-Analyse bestehender CSV ────────────────────────────────

def analysiere_mit_auto_scorer(csv_path: str) -> dict:
    import csv as csv_module
    from pathlib import Path

    path = Path(csv_path)
    if not path.exists():
        print(f"❌ CSV nicht gefunden: {csv_path}")
        return {}

    with open(path, "r", encoding="utf-8") as f:
        daten = list(csv_module.DictReader(f))

    stats = {
        "gesamt": 0,
        "automatisch": 0,
        "grauzone": 0,
        "score_verteilung": {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0},
        "korrekt_vs_manuell": {"korrekt": 0, "falsch": 0, "kein_vergleich": 0}
    }

    for row in daten:
        stats["gesamt"] += 1
        try:
            bert = float(row.get("antwort_bert", "") or 0)
            chunk_bert = float(row.get("max_chunk_bert", "") or 0)
            delta = float(row.get("delta", "") or 0)
            rouge = float(row.get("antwort_rougeL", "") or 0)
            chunk_rouge = float(row.get("max_chunk_rougeL", "") or 0)
        except ValueError:
            stats["grauzone"] += 1
            continue

        auto = row.get("auto_score", "")
        antwort = row.get("generierte_antwort", "")

        result = berechne_auto_score(
            antwort=antwort,
            antwort_bert=bert,
            max_chunk_bert=chunk_bert,
            delta=delta,
            antwort_rougeL=rouge,
            max_chunk_rougeL=chunk_rouge,
            auto_score_ausweich=0 if auto == "0" else None,
            referenz=row.get("referenzantwort", "")
        )

        if result["manuell"]:
            stats["grauzone"] += 1
        else:
            stats["automatisch"] += 1
            if result["score"] is not None:
                stats["score_verteilung"][result["score"]] += 1

            manuell = row.get("score_manuell", "")
            if manuell in ("0", "1", "2"):
                echter = int(manuell)
                auto_score = result["score"]
                if (echter == 0 and auto_score in (0, 1, 4, 5)) or \
                   (echter == 1 and auto_score == 2) or \
                   (echter == 2 and auto_score == 3):
                    stats["korrekt_vs_manuell"]["korrekt"] += 1
                else:
                    stats["korrekt_vs_manuell"]["falsch"] += 1
            else:
                stats["korrekt_vs_manuell"]["kein_vergleich"] += 1

    return stats


# ── Standalone ────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SUSI Auto-Scorer")
    parser.add_argument("--csv", help="CSV auf bestehende Daten anwenden")
    args = parser.parse_args()

    if args.csv:
        stats = analysiere_mit_auto_scorer(args.csv)
        gesamt = stats["gesamt"]
        auto = stats["automatisch"]
        grau = stats["grauzone"]

        print(f"\n{'='*60}")
        print(f"📊 AUTO-SCORER ANALYSE")
        print(f"{'='*60}")
        print(f"   Gesamt          : {gesamt}")
        print(f"   Automatisch     : {auto} ({auto/gesamt*100:.1f}%)")
        print(f"   Grauzone        : {grau} ({grau/gesamt*100:.1f}%)")
        print(f"   MAX_SCORE       : {MAX_SCORE}")
        print(f"   KORREKT_THRESHOLD: {KORREKT_THRESHOLD}")
        print(f"\n   Score-Verteilung (automatisch):")
        labels = {0:"Ausweich", 1:"Halluz", 2:"Training", 3:"RAG✅", 4:"RAGGen", 5:"RAGChunk", 6:"VCKonfl"}
        for s, n in stats["score_verteilung"].items():
            if n > 0:
                print(f"   Score {s} ({labels[s]:<12}): {n}")
        k = stats["korrekt_vs_manuell"]
        if k["korrekt"] + k["falsch"] > 0:
            acc = k["korrekt"] / (k["korrekt"] + k["falsch"]) * 100
            print(f"\n   Genauigkeit vs manuell: {acc:.1f}%")
        print(f"{'='*60}")
    else:
        print("Verwendung: python auto_scorer.py --csv pfad/zur/eval.csv")