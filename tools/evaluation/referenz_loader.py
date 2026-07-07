"""
SUSI Evaluation — Referenz-Loader
==================================
Rendert dynamische Platzhalter in Referenzantworten zur Laufzeit,
damit hartcodierte "heute"-Daten nicht ab dem nächsten Tag veralten.

Anwendungsfall: Testfragen wie "Wie viele Tage seit dem 15. Mai?"
Die Referenz enthält "vom 15. Mai bis heute" — dieses "heute" muss
zur Laufzeit dem tatsächlichen Datum entsprechen, sonst produziert
das Testset ab dem Folgetag systematisch falsche Bewertungen.

Verwendung im JSON:
    {
      "id": "datum_03",
      "frage": "Wenn etwas in exakt 3 Wochen ab heute abläuft, ...",
      "referenz_template": "Heute ist der {heute}. In exakt 3 Wochen (21 Tage) ist das der {heute+21}."
    }

Fragen ohne Template behalten das alte Feld "referenz"/"referenzantwort"
unverändert — nur zeitabhängige Fragen brauchen Templates.

Unterstützte Platzhalter (heute = date.today()):

    {heute}              →  "30. Juni 2026"
    {heute_kurz}         →  "30.06.2026"
    {heute_iso}          →  "2026-06-30"
    {heute_wt}           →  "Dienstag"

    {heute+N}            →  Datum + N Tage, lang: "21. Juli 2026"
    {heute-N}            →  Datum - N Tage
    {heute+N_kurz}       →  Datum + N Tage, kurz: "21.07.2026"
    {heute+N_wt}         →  Wochentag von heute + N Tagen

    {tage_seit:JJJJ-MM-TT}   →  ganze Tage seit dem Datum, integer
    {wochen_bis:JJJJ-MM-TT}  →  ganze Wochen bis zum Datum, integer
    {monate_seit:JJJJ-MM-TT} →  ganze Monate seit dem Datum, integer

N ist eine positive Ganzzahl. Datumswerte im ISO-Format.
Unbekannte Platzhalter bleiben unverändert stehen und werfen keinen
Fehler — bewusst, damit ein einzelner Tippfehler den ganzen Lauf nicht
abbricht (der ValueCheck-Grund im Log zeigt es dann eindeutig).
"""

from __future__ import annotations
import re
from datetime import date, timedelta


MONATE_LANG = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
               "Juli", "August", "September", "Oktober", "November", "Dezember"]

WOCHENTAGE_LANG = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
                   "Freitag", "Samstag", "Sonntag"]


# ── Formatierer ───────────────────────────────────────────────────

def _lang(d: date) -> str:
    return f"{d.day}. {MONATE_LANG[d.month]} {d.year}"

def _kurz(d: date) -> str:
    return f"{d.day:02d}.{d.month:02d}.{d.year}"

def _iso(d: date) -> str:
    return d.isoformat()

def _wt(d: date) -> str:
    return WOCHENTAGE_LANG[d.weekday()]


# ── Differenzen ───────────────────────────────────────────────────

def _monate_diff(von: date, bis: date) -> int:
    """Ganze Monate zwischen zwei Daten. Berücksichtigt den Tag im
    Monat: vom 20.03. bis 30.06. sind es 3 Monate, vom 20.03. bis
    19.06. nur 2. Immer positiv, egal welches Datum größer ist."""
    if von > bis:
        von, bis = bis, von
    monate = (bis.year - von.year) * 12 + (bis.month - von.month)
    if bis.day < von.day:
        monate -= 1
    return monate


def _tage_diff(von: date, bis: date) -> int:
    return abs((bis - von).days)


def _wochen_diff(von: date, bis: date) -> int:
    return _tage_diff(von, bis) // 7


# ── Rendering ─────────────────────────────────────────────────────

def rendere(template: str, heute: date | None = None) -> str:
    """Ersetzt alle bekannten Platzhalter in template durch berechnete
    Werte. heute wird nur für Tests explizit gesetzt, sonst aktuelles
    Datum."""
    if not template:
        return template
    if heute is None:
        heute = date.today()

    text = template

    # Feste Platzhalter für "heute"
    text = text.replace("{heute_kurz}", _kurz(heute))
    text = text.replace("{heute_iso}", _iso(heute))
    text = text.replace("{heute_wt}", _wt(heute))
    text = text.replace("{heute}", _lang(heute))

    # {heute+N} / {heute-N} und Varianten (_kurz, _wt)
    def _rel_wt(m):
        n = int(m.group(1)) * (-1 if m.group(0).find("-") != -1 else 1)
        # negatives Vorzeichen aus dem Match rekonstruieren:
        vorzeichen = -1 if "-" in m.group(0)[:8] else 1
        n = int(m.group(1)) * vorzeichen
        return _wt(heute + timedelta(days=n))

    def _rel_kurz(m):
        vorzeichen = -1 if "-" in m.group(0)[:8] else 1
        n = int(m.group(1)) * vorzeichen
        return _kurz(heute + timedelta(days=n))

    def _rel(m):
        vorzeichen = -1 if "-" in m.group(0)[:8] else 1
        n = int(m.group(1)) * vorzeichen
        return _lang(heute + timedelta(days=n))

    text = re.sub(r"\{heute([+-])(\d+)_wt\}",
                  lambda m: _wt(heute + timedelta(
                      days=int(m.group(2)) * (1 if m.group(1) == "+" else -1))),
                  text)
    text = re.sub(r"\{heute([+-])(\d+)_kurz\}",
                  lambda m: _kurz(heute + timedelta(
                      days=int(m.group(2)) * (1 if m.group(1) == "+" else -1))),
                  text)
    text = re.sub(r"\{heute([+-])(\d+)\}",
                  lambda m: _lang(heute + timedelta(
                      days=int(m.group(2)) * (1 if m.group(1) == "+" else -1))),
                  text)

    # {tage_seit:JJJJ-MM-TT}
    def _tage_seit(m):
        d = date.fromisoformat(m.group(1))
        return str(_tage_diff(d, heute))
    text = re.sub(r"\{tage_seit:(\d{4}-\d{2}-\d{2})\}", _tage_seit, text)

    def _wochen_bis(m):
        d = date.fromisoformat(m.group(1))
        return str(_wochen_diff(heute, d))
    text = re.sub(r"\{wochen_bis:(\d{4}-\d{2}-\d{2})\}", _wochen_bis, text)

    def _monate_seit(m):
        d = date.fromisoformat(m.group(1))
        return str(_monate_diff(d, heute))
    text = re.sub(r"\{monate_seit:(\d{4}-\d{2}-\d{2})\}", _monate_seit, text)

    return text


def rendere_frage(frage: dict, heute: date | None = None) -> dict:
    """Rendert das Referenz-Template einer Frage, falls vorhanden.
    Schreibt das Ergebnis nach 'referenz' und 'referenzantwort' und
    entfernt das Template. Fragen ohne Template bleiben unverändert."""
    tpl = frage.get("referenz_template")
    if not tpl:
        return frage
    gerendert = rendere(tpl, heute)
    frage["referenz"] = gerendert
    frage["referenzantwort"] = gerendert
    return frage


# ── Standalone-Test ───────────────────────────────────────────────

if __name__ == "__main__":
    beispiele = [
        "Heute ist der {heute}.",
        "Heute ist der {heute_kurz} ({heute_wt}).",
        "In 3 Wochen: {heute+21}.",
        "Kurzform: {heute+21_kurz}, Wochentag: {heute+21_wt}.",
        "Vor 15 Tagen: {heute-15}.",
        "Seit dem 15. Mai 2026: {tage_seit:2026-05-15} Tage.",
        "Bis Weihnachten 2026: {wochen_bis:2026-12-25} Wochen.",
        "Seit dem 20. März 2026: {monate_seit:2026-03-20} Monate.",
    ]
    for b in beispiele:
        print(f"{b}")
        print(f"   → {rendere(b)}\n")
        