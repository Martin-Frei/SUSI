"""
SUSI Evaluation — ValueCheck
=============================
Deterministische Prüf-Schicht für den Auto-Scorer.
Extrahiert Zahlen, Daten und Wochentage aus Referenz und SUSI-Antwort
und vergleicht sie direkt — Wert gegen Wert, nicht Text gegen Text.

Hintergrund: BERT-Score und ROUGE-L messen Textähnlichkeit und sind blind
für numerische Fehler in fließend formulierten Antworten (Befund aus
eval_20260630_1218: 10/10 Datumsfragen auto_score=3, real 5/10 falsch).

Skala: ValueCheck arbeitet auf der Diagnostic-Skala (0-5).
    Sicherer Fehler  →  Diagnostic Score 1 (Halluzination / falscher Wert)
    Sicher korrekt   →  gibt frei, bestehender ROUGE/BERT-Baum übernimmt
    Grauzone         →  manuell=True, geht den normalen RAGAS/Haiku-Weg
Das Mapping auf die Quality-Skala (0-2) bleibt unverändert bei den
bestehenden drei Mapping-Stellen (grid_run, ragas_scorer, analyse_csv).

Vergleichsregeln (aus dem ValueCheck-Konzeptpapier, Stand 06.07.2026):
    - Keine Rundungstoleranz, Vergleich exakt
    - Extra-Werte in der Antwort werden ignoriert (Frage 5)
    - Referenz-Wert fehlt + Antwort hat ABWEICHENDE Extra-Werte gleichen
      Typs → falsch (Substitution)
    - Referenz-Wert fehlt + keine abweichenden Extras → Grauzone (Frage 6)
    - Unterschiedliche Datums-Granularität → Grauzone (Frage 3)
    - Wochentage (DE/EN) als eigene Wertklasse (Enum 1-7)
    - Deutsche Zahlwörter zwei bis zwölf (ein/eine bewusst ausgenommen —
      Artikel-Kollision)
    - Jahres-Erkennung nur im Bereich 1990-2035 (sonst wäre chunk_size=1000
      ein "Jahr")

Standalone-Test:
    python tools/evaluation/valuecheck.py \
        --referenz "Der 31.12.1999 war ein Freitag." \
        --antwort  "Das war ein Samstag."
"""

from __future__ import annotations
import re
from typing import Optional


# ── Konstanten ────────────────────────────────────────────────────

WOCHENTAGE = {
    "montag": 1, "monday": 1,
    "dienstag": 2, "tuesday": 2,
    "mittwoch": 3, "wednesday": 3,
    "donnerstag": 4, "thursday": 4,
    "freitag": 5, "friday": 5,
    "samstag": 6, "sonnabend": 6, "saturday": 6,
    "sonntag": 7, "sunday": 7,
}
WOCHENTAG_NAMEN = {1: "Montag", 2: "Dienstag", 3: "Mittwoch", 4: "Donnerstag",
                   5: "Freitag", 6: "Samstag", 7: "Sonntag"}

MONATE = {
    "januar": 1, "january": 1, "jänner": 1,
    "februar": 2, "february": 2,
    "märz": 3, "maerz": 3, "march": 3,
    "april": 4,
    "mai": 5, "may": 5,
    "juni": 6, "june": 6,
    "juli": 7, "july": 7,
    "august": 8,
    "september": 9,
    "oktober": 10, "october": 10,
    "november": 11,
    "dezember": 12, "december": 12,
}
_MONAT_ALT = "|".join(sorted(MONATE.keys(), key=len, reverse=True))

# Zahlwörter zwei bis zwölf. "ein/eine" bewusst NICHT dabei:
# im Deutschen fast immer Artikel ("ein lokaler Assistent"), würde
# massenhaft False Positives erzeugen.
ZAHLWOERTER = {
    "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "fuenf": 5,
    "sechs": 6, "sieben": 7, "acht": 8, "neun": 9,
    "zehn": 10, "elf": 11, "zwölf": 12, "zwoelf": 12,
}
_ZAHLWORT_ALT = "|".join(sorted(ZAHLWOERTER.keys(), key=len, reverse=True))

# Anfang/Mitte/Ende: Anfang=Q1, Mitte=Q2+Q3, Ende=Q4 (Konzept, Q3-Fix)
QUARTAL_WOERTER = {
    "anfang": frozenset({1, 2, 3}),
    "mitte": frozenset({4, 5, 6, 7, 8, 9}),
    "ende": frozenset({10, 11, 12}),
}
QUARTAL_KUERZEL = {
    "q1": frozenset({1, 2, 3}),
    "q2": frozenset({4, 5, 6}),
    "q3": frozenset({7, 8, 9}),
    "q4": frozenset({10, 11, 12}),
}

# Jahres-Erkennung nur in plausibler Range — sonst wird chunk_size=1000
# oder Port 11434 als "Jahr" typisiert.
JAHR_MIN, JAHR_MAX = 1990, 2035


# ── Extraktion ────────────────────────────────────────────────────

def extrahiere_werte(text: str) -> dict:
    """
    Extrahiert alle vergleichbaren Werte aus einem Text.

    Returns:
        {
            "wochentage":  set[int],          # 1-7
            "daten_voll":  set[(d, m, y)],    # 30.06.2026 / 30. Juni 2026
            "daten_monat": set[(m, y)],       # 07.2026 / Juli 2026
            "quartale":    set[(frozenset_monate, y)],
            "jahre":       set[int],          # 1990-2035, alleinstehend
            "zahlen":      set[float],        # inkl. Zahlwörter 2-12
        }
    Reihenfolge: spezifischste Muster zuerst, gematchte Spans werden
    maskiert damit z.B. die "30" aus "30.06.2026" nicht nochmal als
    Einzelzahl gezählt wird.
    """
    if not text:
        return _leere_werte()

    werte = _leere_werte()
    t = text

    # 1) Wochentage
    def _wd(m):
        werte["wochentage"].add(WOCHENTAGE[m.group(0).lower()])
        return " " * len(m.group(0))
    t = re.sub(r"\b(" + "|".join(WOCHENTAGE.keys()) + r")s?\b",
               _wd, t, flags=re.IGNORECASE)

    # 2) Volle Daten — numerisch: 30.06.2026 / 5.3.2026
    def _dv_num(m):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= d <= 31 and 1 <= mo <= 12:
            werte["daten_voll"].add((d, mo, y))
            return " " * len(m.group(0))
        return m.group(0)
    t = re.sub(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", _dv_num, t)

    # 2b) Volle Daten — Wort: "30. Juni 2026" / "31. Dezember 1999"
    def _dv_wort(m):
        d = int(m.group(1))
        mo = MONATE[m.group(2).lower()]
        y = int(m.group(3))
        if 1 <= d <= 31:
            werte["daten_voll"].add((d, mo, y))
            return " " * len(m.group(0))
        return m.group(0)
    t = re.sub(r"\b(\d{1,2})\.\s*(" + _MONAT_ALT + r")\s+(\d{4})\b",
               _dv_wort, t, flags=re.IGNORECASE)

    # 3) Monats-Daten — Wort: "Juli 2026" / numerisch: "07.2026"
    def _dm_wort(m):
        werte["daten_monat"].add((MONATE[m.group(1).lower()], int(m.group(2))))
        return " " * len(m.group(0))
    t = re.sub(r"\b(" + _MONAT_ALT + r")\s+(\d{4})\b",
               _dm_wort, t, flags=re.IGNORECASE)

    def _dm_num(m):
        mo, y = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and JAHR_MIN <= y <= JAHR_MAX:
            werte["daten_monat"].add((mo, y))
            return " " * len(m.group(0))
        return m.group(0)
    t = re.sub(r"\b(\d{1,2})\.(\d{4})\b", _dm_num, t)

    # 4) Quartale: "Anfang 2026", "Q3 2026"
    def _qw(m):
        werte["quartale"].add((QUARTAL_WOERTER[m.group(1).lower()],
                               int(m.group(2))))
        return " " * len(m.group(0))
    t = re.sub(r"\b(Anfang|Mitte|Ende)\s+(\d{4})\b", _qw, t,
               flags=re.IGNORECASE)

    def _qk(m):
        werte["quartale"].add((QUARTAL_KUERZEL[m.group(1).lower()],
                               int(m.group(2))))
        return " " * len(m.group(0))
    t = re.sub(r"\b(Q[1-4])\s+(\d{4})\b", _qk, t, flags=re.IGNORECASE)

    # 5) Alleinstehende Jahre (plausible Range)
    def _jahr(m):
        y = int(m.group(0))
        if JAHR_MIN <= y <= JAHR_MAX:
            werte["jahre"].add(y)
            return " " * len(m.group(0))
        return m.group(0)
    t = re.sub(r"\b\d{4}\b", _jahr, t)

    # 6) Zahlwörter zwei-zwölf
    def _zw(m):
        werte["zahlen"].add(float(ZAHLWOERTER[m.group(0).lower()]))
        return " " * len(m.group(0))
    t = re.sub(r"\b(" + _ZAHLWORT_ALT + r")\b", _zw, t, flags=re.IGNORECASE)

    # 7) Restliche Zahlen (int + dezimal, Komma oder Punkt)
    for m in re.finditer(r"\b\d+(?:[.,]\d+)?\b", t):
        werte["zahlen"].add(float(m.group(0).replace(",", ".")))

    return werte


def _leere_werte() -> dict:
    return {"wochentage": set(), "daten_voll": set(), "daten_monat": set(),
            "quartale": set(), "jahre": set(), "zahlen": set()}


def _hat_werte(w: dict) -> bool:
    return any(w[k] for k in w)


# ── Vergleich ─────────────────────────────────────────────────────

def pruefe_werte(referenz: str, antwort: str) -> dict:
    """
    Vergleicht die extrahierten Werte aus Referenz und Antwort.

    Returns:
        {
            "status": "inaktiv" | "korrekt" | "falsch" | "grauzone",
            "grund":  str
        }

    Entscheidungslogik pro Referenz-Wert:
        gefunden                          → ok
        fehlt + abweichende Extras da     → FALSCH (Substitution)
        fehlt + keine abweichenden Extras → GRAUZONE (unvollständig?)
        Datum in anderer Granularität     → GRAUZONE
    Ein einziger harter Fehler macht die ganze Antwort falsch (Frage 4).
    Extra-Werte der Antwort die in der Referenz vorkommen: ignoriert (Frage 5).
    """
    ref = extrahiere_werte(referenz or "")
    ans = extrahiere_werte(antwort or "")

    if not _hat_werte(ref):
        return {"status": "inaktiv",
                "grund": "Referenz enthält keine prüfbaren Werte"}
    if not _hat_werte(ans):
        return {"status": "grauzone",
                "grund": "Referenz enthält Werte, Antwort keine — "
                         "sinngemäße Antwort ohne Zahl?"}

    fehler: list[str] = []
    grauzone: list[str] = []

    # ── Wochentage ────────────────────────────────────────────
    for wd in ref["wochentage"]:
        if wd in ans["wochentage"]:
            continue
        abweichend = ans["wochentage"] - ref["wochentage"]
        if abweichend:
            fehler.append(
                f"Wochentagsabweichung: Referenz={WOCHENTAG_NAMEN[wd]}, "
                f"Antwort={'/'.join(WOCHENTAG_NAMEN[a] for a in sorted(abweichend))}")
        else:
            grauzone.append(f"Wochentag {WOCHENTAG_NAMEN[wd]} fehlt in Antwort")

    # ── Volle Daten ───────────────────────────────────────────
    for d in ref["daten_voll"]:
        if d in ans["daten_voll"]:
            continue
        abweichend = ans["daten_voll"] - ref["daten_voll"]
        if abweichend:
            a = sorted(abweichend)[0]
            fehler.append(
                f"Datumsabweichung: Referenz={_fmt_voll(d)}, "
                f"Antwort enthält {_fmt_voll(a)}")
        elif ans["daten_monat"] or ans["jahre"]:
            grauzone.append(
                f"Granularität: Referenz={_fmt_voll(d)}, "
                f"Antwort nur Monat/Jahr")
        else:
            grauzone.append(f"Datum {_fmt_voll(d)} fehlt in Antwort")

    # ── Monats-Daten ──────────────────────────────────────────
    for d in ref["daten_monat"]:
        if d in ans["daten_monat"]:
            continue
        # Antwort präziser als Referenz (März 2026 vs 15.03.2026)?
        praeziser = any((mo, y) == d for (_t, mo, y) in ans["daten_voll"])
        if praeziser:
            grauzone.append(
                f"Granularität: Referenz={_fmt_monat(d)}, "
                f"Antwort nennt Tagesdatum im selben Monat")
            continue
        abweichend = ans["daten_monat"] - ref["daten_monat"]
        if abweichend:
            a = sorted(abweichend)[0]
            fehler.append(
                f"Monatsabweichung: Referenz={_fmt_monat(d)}, "
                f"Antwort enthält {_fmt_monat(a)}")
        else:
            grauzone.append(f"Monatsdatum {_fmt_monat(d)} fehlt in Antwort")

    # ── Quartale ──────────────────────────────────────────────
    for (monate, jahr) in ref["quartale"]:
        treffer = any(y == jahr and mo in monate
                      for (mo, y) in ans["daten_monat"])
        treffer = treffer or any(y == jahr and mo in monate
                                 for (_d, mo, y) in ans["daten_voll"])
        if treffer:
            continue
        daneben = any(y == jahr and mo not in monate
                      for (mo, y) in ans["daten_monat"])
        daneben = daneben or any(y == jahr and mo not in monate
                                 for (_d, mo, y) in ans["daten_voll"])
        if daneben:
            fehler.append(
                f"Quartalsabweichung: Referenz erlaubt Monate "
                f"{sorted(monate)} in {jahr}, Antwort liegt daneben")
        else:
            gleich = any(q == (monate, jahr) for q in ans["quartale"])
            if gleich:
                continue
            grauzone.append(f"Quartalsangabe {jahr} nicht vergleichbar")

    # ── Alleinstehende Jahre ──────────────────────────────────
    ans_jahre_gesamt = (set(ans["jahre"])
                        | {y for (_d, _m, y) in ans["daten_voll"]}
                        | {y for (_m, y) in ans["daten_monat"]}
                        | {y for (_q, y) in ans["quartale"]})
    ref_jahre_gesamt = (set(ref["jahre"])
                        | {y for (_d, _m, y) in ref["daten_voll"]}
                        | {y for (_m, y) in ref["daten_monat"]}
                        | {y for (_q, y) in ref["quartale"]})
    for y in ref["jahre"]:
        if y in ans_jahre_gesamt:
            continue
        abweichend = ans_jahre_gesamt - ref_jahre_gesamt
        if abweichend:
            fehler.append(
                f"Jahresabweichung: Referenz={y}, "
                f"Antwort enthält {sorted(abweichend)}")
        else:
            grauzone.append(f"Jahr {y} fehlt in Antwort")

    # ── Zahlen ────────────────────────────────────────────────
    for n in ref["zahlen"]:
        if n in ans["zahlen"]:
            continue
        abweichend = ans["zahlen"] - ref["zahlen"]
        if abweichend:
            fehler.append(
                f"Zahlenabweichung: Referenz={_fmt_zahl(n)} fehlt, "
                f"Antwort enthält {[_fmt_zahl(a) for a in sorted(abweichend)]}")
        else:
            grauzone.append(f"Zahl {_fmt_zahl(n)} fehlt in Antwort")

    # ── Ergebnis ──────────────────────────────────────────────
    if fehler:
        return {"status": "falsch", "grund": "; ".join(fehler[:3])}
    if grauzone:
        return {"status": "grauzone", "grund": "; ".join(grauzone[:3])}
    return {"status": "korrekt", "grund": "Alle Referenz-Werte gefunden"}


# ── Formatierung ──────────────────────────────────────────────────

def _fmt_voll(d) -> str:
    return f"{d[0]:02d}.{d[1]:02d}.{d[2]}"

def _fmt_monat(d) -> str:
    return f"{d[0]:02d}.{d[1]}"

def _fmt_zahl(n: float) -> str:
    return str(int(n)) if n == int(n) else str(n)


# ── Standalone ────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SUSI ValueCheck")
    parser.add_argument("--referenz", required=True)
    parser.add_argument("--antwort", required=True)
    args = parser.parse_args()

    ref_w = extrahiere_werte(args.referenz)
    ans_w = extrahiere_werte(args.antwort)
    print(f"Referenz-Werte: { {k: v for k, v in ref_w.items() if v} }")
    print(f"Antwort-Werte:  { {k: v for k, v in ans_w.items() if v} }")
    ergebnis = pruefe_werte(args.referenz, args.antwort)
    print(f"\nStatus: {ergebnis['status'].upper()}")
    print(f"Grund:  {ergebnis['grund']}")