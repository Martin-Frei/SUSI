"""
SUSI Evaluation — ValueCheck Validierung
=========================================
Läuft ValueCheck gegen eine bestehende Eval-CSV und zeigt pro Zeile
das Urteil. Kein Ollama, kein LLM — rein deterministisch, läuft überall.

Aufruf:
    python tools/evaluation/test_valuecheck.py --csv tools/evaluation/results/eval_20260630_1218_full.csv
"""

import csv
import argparse
from valuecheck import pruefe_werte, extrahiere_werte

# Erwartete Ergebnisse für das Datumsarithmetik-Set (manuell verifiziert,
# 30.06.2026). "falsch" = Antwort faktisch falsch, "korrekt" = faktisch richtig.
ERWARTET = {
    "datum_01": "falsch",    # 10 Monate statt 3
    "datum_02": "falsch",    # verwirrte Antwort, 46 fehlt
    "datum_03": "korrekt",   # 21.07.2026 korrekt
    "datum_04": "korrekt",   # "über 7 Monate" — grenzwertig, Kern stimmt
    "datum_05": "falsch",    # Samstag statt Freitag
    "datum_06": "falsch",    # Samstag statt Freitag
    "datum_07": "falsch",    # 1 Tag statt 29
    "datum_08": "falsch",    # 07.07. statt 14.07.
    "datum_09": "falsch",    # logischer Fehler — außerhalb ValueCheck-Scope
    "datum_10": "falsch",    # 26 Wochen statt 25 (Rechnung inkonsistent)
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--verbose", action="store_true",
                        help="Extrahierte Werte pro Zeile anzeigen")
    args = parser.parse_args()

    with open(args.csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"\n{'='*72}")
    print(f"VALUECHECK VALIDIERUNG — {len(rows)} Zeilen")
    print(f"{'='*72}")

    stats = {"falsch": 0, "grauzone": 0, "korrekt": 0, "inaktiv": 0}
    false_positive_verhindert = 0

    for row in rows:
        fid = row.get("frage_id", "?")
        ref = row.get("referenzantwort", "")
        ans = row.get("generierte_antwort", "")
        auto = row.get("auto_score", "")

        ergebnis = pruefe_werte(ref, ans)
        status = ergebnis["status"]
        stats[status] += 1

        erwartet = ERWARTET.get(fid, "?")
        # Erfolg = eine faktisch falsche Antwort landet NICHT bei "korrekt"
        if erwartet == "falsch" and status in ("falsch", "grauzone"):
            symbol = "✅"
            false_positive_verhindert += 1
        elif erwartet == "korrekt" and status in ("korrekt", "grauzone", "inaktiv"):
            symbol = "✅"
        elif erwartet == "falsch" and status == "korrekt":
            symbol = "❌ FALSE POSITIVE"
        else:
            symbol = "⚠️"

        print(f"\n{symbol} {fid}  [alter auto_score={auto}]")
        print(f"   ValueCheck: {status.upper()} — {ergebnis['grund']}")
        print(f"   (real: {erwartet})")
        if args.verbose:
            rw = {k: v for k, v in extrahiere_werte(ref).items() if v}
            aw = {k: v for k, v in extrahiere_werte(ans).items() if v}
            print(f"   Ref-Werte: {rw}")
            print(f"   Ans-Werte: {aw}")

    print(f"\n{'='*72}")
    print(f"ZUSAMMENFASSUNG")
    print(f"{'='*72}")
    print(f"   falsch (hart, Diagnostic 1):     {stats['falsch']}")
    print(f"   grauzone (→ RAGAS/Haiku):        {stats['grauzone']}")
    print(f"   korrekt (→ ROUGE/BERT-Baum):     {stats['korrekt']}")
    print(f"   inaktiv:                          {stats['inaktiv']}")
    n_falsch = sum(1 for v in ERWARTET.values() if v == "falsch")
    print(f"\n   Faktisch falsche Antworten nicht mehr als 'korrekt' durchgewunken:")
    print(f"   {false_positive_verhindert}/{n_falsch}")
    print(f"   (Vorher: Auto-Scorer gab allen 10 Zeilen auto_score=3)")


if __name__ == "__main__":
    main()
    