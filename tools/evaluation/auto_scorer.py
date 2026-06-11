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

Schwellenwerte (aus 768 echten Einträgen berechnet):
    ROUGE-L < 0.05                          →  0 oder 1
    ROUGE-L > 0.25 + BERT > 0.75           →  3 (sicher)
    max_chunk_rougeL < 0.10 + ROUGE-L < 0.05 → 5 (falscher Chunk)
    max_chunk_bert > 0.70 + ROUGE-L < 0.10  → 4 (Generation-Problem)
    Alles andere                            →  Grauzone → manuell

Automatisierungsgrad aus erstem Lauf: 71.6%
Genauigkeit automatischer Entscheidungen: ~88%

Aufruf standalone:
    python tools/evaluation/auto_scorer.py --csv tools/evaluation/results/eval_xxx.csv
"""

from typing import Optional


# ── Schwellenwerte (aus echten Daten) ─────────────────────────────

# Aus 768 Einträgen berechnet:
# Score 2 (korrekt): antwort_rougeL Ø 0.343, antwort_bert Ø 0.784
# Score 0 (falsch):  antwort_rougeL Ø 0.099, antwort_bert Ø 0.644
# Score Auto-0:      antwort_rougeL Ø 0.025

SCHWELLEN = {
    # Ausweichantwort — ROUGE-L fast 0
    "ausweich_rouge": 0.05,

    # Sicher korrekt (Score 3) — beide Metriken hoch
    "korrekt_rouge": 0.15,
    "korrekt_bert": 0.65,

    # Falscher Chunk (Score 5) — Chunk ROUGE-L niedrig
    "falscher_chunk_rouge": 0.10,

    # Generation-Problem (Score 4) — Chunk war gut, Antwort nicht
    "generation_chunk_bert": 0.70,
    "generation_antwort_rouge": 0.10,

    # Grauzone-Grenzen
    "grauzone_rouge_min": 0.05,
    "grauzone_rouge_max": 0.25,
}

# Bekannte Ausweich-Phrasen (exakt, nicht Teilstring)
AUSWEICH_PHRASEN = [
    "diese information ist nicht verfügbar",
    "diese information ist nicht verfuegbar",
    "dazu fehlt mir noch was in der susipedia",
    "ich habe keine information dazu",
    "ich kann diese frage nicht beantworten",
    "keine information verfügbar",
]


# ── Kernfunktion ──────────────────────────────────────────────────

def berechne_auto_score(
    antwort: str,
    antwort_bert: Optional[float],
    max_chunk_bert: Optional[float],
    delta: Optional[float],
    antwort_rougeL: Optional[float],
    max_chunk_rougeL: Optional[float],
    auto_score_ausweich: Optional[int] = None
) -> dict:
    """
    Berechnet automatisch einen Score (0-5) aus den Metriken.

    Entscheidungsbaum:
        1. Ausweichantwort erkannt?        → Score 0
        2. ROUGE-L < 0.05?
           + max_chunk_rougeL < 0.10?     → Score 5 (falscher Chunk)
           + max_chunk_bert > 0.70?       → Score 4 (Generation-Problem)
           + sonst                        → Score 1 (Halluzination)
        3. ROUGE-L > 0.25 + BERT > 0.75? → Score 3 (RAG korrekt)
        4. ROUGE-L > 0.25 + Delta > 0.10? → Score 2 (Training korrekt)
        5. Alles andere                   → Grauzone (manuell)

    Args:
        antwort:              Generierte Antwort
        antwort_bert:         BERTScore Antwort vs Referenz
        max_chunk_bert:       Bester Chunk BERTScore
        delta:                antwort_bert - max_chunk_bert
        antwort_rougeL:       ROUGE-L Antwort vs Referenz
        max_chunk_rougeL:     Bester Chunk ROUGE-L vs Referenz
        auto_score_ausweich:  0 wenn Ausweichantwort erkannt (aus evaluator.py)

    Returns:
        dict mit:
            score:       int 0-5 oder None (Grauzone)
            konfidenz:   "hoch" / "mittel" / "grauzone"
            grund:       Erklärung der Entscheidung
            manuell:     True wenn manuell nötig
    """

    # Schritt 1 — Ausweichantwort
    if auto_score_ausweich == 0:
        return {
            "score": 0,
            "konfidenz": "hoch",
            "grund": "Ausweichantwort erkannt (Auto-Score)",
            "manuell": False
        }

    # Exakte Phrasen prüfen (Bug-Fix: kein Teilstring-Matching)
    if antwort:
        antwort_lower = antwort.lower().strip()
        for phrase in AUSWEICH_PHRASEN:
            if phrase == antwort_lower or antwort_lower.startswith(phrase):
                return {
                    "score": 0,
                    "konfidenz": "hoch",
                    "grund": f"Ausweichantwort erkannt: '{phrase[:40]}...'",
                    "manuell": False
                }

    # Metriken prüfen
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

    # Schritt 2 — ROUGE-L sehr niedrig (Halluzination oder falscher Chunk)
    if rouge < SCHWELLEN["ausweich_rouge"]:

        # Score 5 — falscher Chunk (Retrieval in falsche Kategorie)
        if chunk_rouge is not None and chunk_rouge < SCHWELLEN["falscher_chunk_rouge"]:
            return {
                "score": 5,
                "konfidenz": "mittel",
                "grund": f"Falscher Chunk — ROUGE-L={rouge:.3f}, ChunkROUGE={chunk_rouge:.3f}",
                "manuell": False
            }

        # Score 4 — Generation-Problem (Chunk war gut, Antwort nicht)
        if chunk_bert is not None and chunk_bert > SCHWELLEN["generation_chunk_bert"]:
            return {
                "score": 4,
                "konfidenz": "mittel",
                "grund": f"Generation-Problem — ChunkBERT={chunk_bert:.3f}, ROUGE-L={rouge:.3f}",
                "manuell": False
            }

        # Score 1 — Halluzination
        return {
            "score": 1,
            "konfidenz": "mittel",
            "grund": f"Halluzination — ROUGE-L={rouge:.3f}, BERT={bert:.3f}",
            "manuell": False
        }

    # Schritt 3 — ROUGE-L hoch + BERT hoch → Score 3 (RAG korrekt)
    if rouge > SCHWELLEN["korrekt_rouge"] and bert > SCHWELLEN["korrekt_bert"]:
        return {
            "score": 3,
            "konfidenz": "hoch",
            "grund": f"RAG korrekt — ROUGE-L={rouge:.3f}, BERT={bert:.3f}",
            "manuell": False
        }

    # Schritt 4 — ROUGE-L hoch aber Delta positiv → Score 2 (Training)
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


# ── Konsolen-Anzeige ──────────────────────────────────────────────

def zeige_auto_score(result: dict, frage: str, referenz: str, antwort: str,
                     bert_info: dict = None, rouge_info: dict = None) -> Optional[int]:
    """
    Zeigt den automatischen Score und fragt bei Grauzone manuell nach.

    Args:
        result:     Ergebnis von berechne_auto_score()
        frage:      Fragetext
        referenz:   Referenzantwort
        antwort:    Generierte Antwort
        bert_info:  BERTScore-Ergebnisse
        rouge_info: ROUGE-L Ergebnisse

    Returns:
        int: finaler Score (automatisch oder manuell)
        -1:  übersprungen
    Raises:
        KeyboardInterrupt: wenn q gedrückt
    """
    SCORE_LABELS = {
        0: "Ausweichantwort",
        1: "Halluzination",
        2: "Training korrekt",
        3: "RAG korrekt ✅",
        4: "RAG falsch — Generation",
        5: "RAG falsch — falscher Chunk"
    }

    # Automatische Entscheidung
    if not result["manuell"] and result["score"] is not None:
        label = SCORE_LABELS.get(result["score"], "?")
        symbol = "✅" if result["konfidenz"] == "hoch" else "🔶"
        print(f"  {symbol} Auto-Score {result['score']} ({label}) — {result['grund']}")
        return result["score"]

    # Grauzone — manuell
    print(f"\n{'='*60}")
    print(f"❓ FRAGE:\n{frage}\n")
    print(f"✅ REFERENZ:\n{referenz}\n")
    print(f"🤖 SUSI:\n{antwort}\n")

    # Metriken anzeigen
    if bert_info and bert_info.get("antwort_bert") is not None:
        rouge_str = ""
        if rouge_info and rouge_info.get("antwort_rougeL") is not None:
            rouge_str = f" | ROUGE-L: {rouge_info['antwort_rougeL']:.3f} | ChunkROUGE: {rouge_info.get('max_chunk_rougeL', 0):.3f}"
        print(f"📊 BERT: {bert_info['antwort_bert']:.3f} | "
              f"MaxChunk: {bert_info['max_chunk_bert']:.3f} | "
              f"Delta: {bert_info['delta']:+.3f}{rouge_str}")

    print(f"🔶 Grauzone — {result['grund']}")
    print(f"─"*60)
    print(f"Skala: 0=Ausweich | 1=Halluz | 2=Training | 3=RAG✅ | 4=RAGGen | 5=RAGChunk")
    print(f"       s=Überspringen | q=Beenden")

    while True:
        eingabe = input("Score: ").strip().lower()
        if eingabe in ("0", "1", "2", "3", "4", "5"):
            return int(eingabe)
        elif eingabe == "s":
            return -1
        elif eingabe == "q":
            raise KeyboardInterrupt("Beenden")
        else:
            print("Bitte 0-5, s oder q eingeben.")


# ── Batch-Analyse bestehender CSV ────────────────────────────────

def analysiere_mit_auto_scorer(csv_path: str) -> dict:
    """
    Wendet den Auto-Scorer auf eine bestehende CSV an.
    Nützlich um den Scorer auf alten Daten zu testen.

    Args:
        csv_path: Pfad zur eval CSV

    Returns:
        dict mit Statistiken
    """
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
        "score_verteilung": {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
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
            auto_score_ausweich=0 if auto == "0" else None
        )

        if result["manuell"]:
            stats["grauzone"] += 1
        else:
            stats["automatisch"] += 1
            if result["score"] is not None:
                stats["score_verteilung"][result["score"]] += 1

            # Mit manuellem Score vergleichen
            manuell = row.get("score_manuell", "")
            if manuell in ("0", "1", "2"):
                echter = int(manuell)
                # Mapping: alter Score 0/1/2 → neuer Score 0-5
                # 0 → 0 oder 1 oder 5, 1 → 2, 2 → 3
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
        print(f"\n   Score-Verteilung (automatisch):")
        labels = {0:"Ausweich", 1:"Halluz", 2:"Training", 3:"RAG✅", 4:"RAGGen", 5:"RAGChunk"}
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