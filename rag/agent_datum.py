"""
SUSI — datum_agent
===================
SUSIs erstes Werkzeug im Sinne von Tool Use / Function Calling.
Erkennt reine Kalenderfragen (Wochentag, Tage zwischen, N Tage/Wochen
ab heute, Wochen bis...) und beantwortet sie deterministisch per Python
datetime, ohne LLM und ohne RAG.

Kontext (siehe docs/susi/valuecheck_und_referenz_loader.md):
    LLMs sind autoregressive Token-Prädiktoren und rechnen strukturell
    unzuverlässig. Der ValueCheck vom 06.07.2026 macht Rechenfehler
    zwar sichtbar, behebt sie aber nicht. Der Datums-Agent ist der
    behebende Teil: Kalenderfragen werden gar nicht erst dem LLM
    vorgelegt, sondern direkt in Python berechnet.

Aufruf in rag/query.py (ganz früh, direkt nach detect_language):
    from rag import datum_agent
    if datum_agent.ist_kalenderfrage(frage):
        return datum_agent.beantworte_kalenderfrage(frage)
    # ab hier normale Pipeline

Konservative Klassifikation — alle drei Bedingungen müssen gelten:
    1. Konkretes Datum oder Datums-Anker in der Frage
       (Datum, "heute", "Weihnachten JJJJ", "Silvester JJJJ" usw.)
    2. Klare Kalender-Operation
       (Wochentag, Tage/Wochen/Monate zwischen, +N Tage/Wochen,
        übernächste Woche etc.)
    3. Kein SUSIpedia-Entitätsname
       (SUSI, StockPredict, GMM, HouseOfStacks, HOS, Portfolio,
        Projekt-Namen, mein/meine)
Im Zweifel → LLM+RAG. Der Agent macht nur was er sicher kann.

Standalone-Test:
    python rag/datum_agent.py --frage "Welcher Wochentag war der 31.12.1999?"
    python rag/datum_agent.py --demo    # Klassifikation der 10 Testfragen
"""

from __future__ import annotations
import re
from datetime import date, timedelta
from typing import Optional


# ── Kalender-Grunddaten (aus referenz_loader wiederverwendet) ────

MONATE_NAMEN = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
                "Juli", "August", "September", "Oktober", "November", "Dezember"]
WOCHENTAG_NAMEN = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
                   "Freitag", "Samstag", "Sonntag"]

MONAT_ZU_NUM = {n.lower(): i for i, n in enumerate(MONATE_NAMEN) if n}
MONAT_ZU_NUM.update({"märz": 3, "maerz": 3})  # Alternativschreibung

# Bekannte Anker für Datumsangaben ohne explizites Datum in der Frage.
# Nur Anker deren Datum kalendrisch fest liegt.
ANKER_TAG_MONAT = {
    "weihnachten": (25, 12),
    "heiligabend": (24, 12),
    "silvester": (31, 12),
    "neujahr": (1, 1),
}


# ── SUSIpedia-Entitäten (Sperrliste für Bedingung 3) ─────────────
# Wenn eines dieser Wörter in der Frage steht → LLM+RAG-Pfad,
# egal wie datumslastig die Frage aussieht.

ENTITAETEN = {
    # Eigene Projekte
    "susi", "stockpredict", "spv2", "sp v2",
    "gmm", "global market mood",
    "houseofstacks", "house of stacks", "hos",
    "portfolio", "portfolio_site",
    # Personen und Bezüge
    "martin", "tanveer", "adeena",
    # Persönliche Referenzen
    "mein", "meine", "meinen", "meines", "meiner",
    "ich", "mir", "mich",
    # Generische Projekt-Wörter — konservative Wahl, damit
    # "wie lange läuft das Projekt schon?" NICHT auf Python geht
    "projekt", "projekts", "projekte",
    "firma", "team", "kollege", "kollegen",
}


# ── Bedingung 1 — Datums-Erkennung ────────────────────────────────

DATUM_MUSTER = [
    # Tag.Monat.Jahr numerisch: 25.12.2026 / 5.3.2026
    re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b"),
    # Tag. Monat Jahr wörtlich: "25. Dezember 2026" / "31. Dezember 1999"
    re.compile(r"\b(\d{1,2})\.\s*("
               + "|".join(MONAT_ZU_NUM.keys())
               + r")\s+(\d{4})\b", re.IGNORECASE),
    # "Weihnachten 2026", "Silvester 2026" mit Jahr
    re.compile(r"\b(" + "|".join(ANKER_TAG_MONAT.keys())
               + r")\s+(\d{4})\b", re.IGNORECASE),
]

HEUTE_MUSTER = re.compile(r"\b(heute|jetzt|aktuell)\b", re.IGNORECASE)


def _hat_datum_oder_anker(text: str) -> bool:
    if HEUTE_MUSTER.search(text):
        return True
    return any(m.search(text) for m in DATUM_MUSTER)


# ── Bedingung 2 — Kalender-Operation erkennen ────────────────────
# Muster reichen bewusst nur wenn eine RECHENOPERATION erkennbar ist.
# Reine Faktenfragen zu einem Datum ("was war am 20.03. passiert?")
# fallen bewusst nicht drunter.

OPERATION_MUSTER = [
    re.compile(r"\bwelcher\s+wochentag\b", re.IGNORECASE),
    re.compile(r"\bwochentag\s+(war|ist|fällt|fiel)\b", re.IGNORECASE),
    # "wie viele Tage ... seit/bis/zwischen" — Zwischenwörter erlaubt
    # (sind, liegen, sind es, hat es noch ...)
    re.compile(r"\bwie\s+viele?\s+tage?\b.{0,40}?\b(seit|bis|zwischen|zw\.)\b",
               re.IGNORECASE),
    re.compile(r"\bwie\s+viele?\s+wochen?\b.{0,40}?\b(seit|bis|zwischen|zw\.|noch)\b",
               re.IGNORECASE),
    re.compile(r"\bwie\s+viele?\s+monate?\b.{0,40}?\b(seit|bis|zwischen|zw\.)\b",
               re.IGNORECASE),
    re.compile(r"\b(in|nach)\s+(exakt\s+)?\d+\s+(tag|tage|woche|wochen)\b",
               re.IGNORECASE),
    re.compile(r"\b(nächste|übernächste|naechste|uebernaechste)\s+woche\b",
               re.IGNORECASE),
    re.compile(r"\bab\s+heute\b", re.IGNORECASE),
]


def _hat_kalender_operation(text: str) -> bool:
    return any(m.search(text) for m in OPERATION_MUSTER)


# ── Bedingung 3 — Keine SUSIpedia-Entität ────────────────────────

def _hat_entitaet(text: str) -> Optional[str]:
    t = text.lower()
    for e in ENTITAETEN:
        if re.search(rf"\b{re.escape(e)}\b", t):
            return e
    return None


# ── öffentliche API — Klassifikation ──────────────────────────────

def ist_kalenderfrage(text: str) -> bool:
    """Konservative Drei-Bedingungen-Klassifikation.
    True nur wenn alle drei zutreffen. Im Zweifel False."""
    if not text or len(text) > 500:  # überlange Fragen sind nie reine Kalender
        return False
    if not _hat_datum_oder_anker(text):
        return False
    if not _hat_kalender_operation(text):
        return False
    if _hat_entitaet(text) is not None:
        return False
    return True


def diagnose(text: str) -> dict:
    """Gibt die Klassifikations-Diagnose zurück — für Testing und Debug."""
    return {
        "datum_oder_anker": _hat_datum_oder_anker(text),
        "kalender_operation": _hat_kalender_operation(text),
        "entitaet": _hat_entitaet(text),
        "ist_kalenderfrage": ist_kalenderfrage(text),
    }


# ── Datums-Parser für die Ausführung ─────────────────────────────

def _parse_datum(text: str) -> list[date]:
    """Extrahiert alle Datumsangaben aus dem Text. Reihenfolge:
    zuerst spezifische Muster (mit Jahr), dann Anker (Weihnachten...)."""
    treffer: list[date] = []

    # Numerisch: 25.12.2026
    for m in re.finditer(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", text):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= d <= 31 and 1 <= mo <= 12:
            try:
                treffer.append(date(y, mo, d))
            except ValueError:
                pass

    # Wörtlich: "31. Dezember 1999"
    for m in re.finditer(
        r"\b(\d{1,2})\.\s*(" + "|".join(MONAT_ZU_NUM.keys()) + r")\s+(\d{4})\b",
        text, re.IGNORECASE
    ):
        d, mo, y = int(m.group(1)), MONAT_ZU_NUM[m.group(2).lower()], int(m.group(3))
        try:
            treffer.append(date(y, mo, d))
        except ValueError:
            pass

    # Anker: "Weihnachten 2026"
    for m in re.finditer(
        r"\b(" + "|".join(ANKER_TAG_MONAT.keys()) + r")\s+(\d{4})\b",
        text, re.IGNORECASE
    ):
        d, mo = ANKER_TAG_MONAT[m.group(1).lower()]
        y = int(m.group(2))
        try:
            treffer.append(date(y, mo, d))
        except ValueError:
            pass

    return treffer


def _formatiere(d: date) -> str:
    return f"{d.day}. {MONATE_NAMEN[d.month]} {d.year}"


def _formatiere_kurz(d: date) -> str:
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


# ── öffentliche API — Ausführung ──────────────────────────────────

def beantworte_kalenderfrage(text: str, heute: Optional[date] = None) -> str:
    """Beantwortet eine reine Kalenderfrage deterministisch.
    Wird nur aufgerufen wenn ist_kalenderfrage() True gesagt hat.
    heute wird nur für Tests explizit gesetzt."""
    if heute is None:
        heute = date.today()

    daten = _parse_datum(text)
    t = text.lower()

    # 1) Wochentag eines konkreten Datums
    if re.search(r"\bwochentag\b", t) and daten:
        d = daten[0]
        verb = "war" if d < heute else "ist"
        return (f"Der {_formatiere(d)} {verb} ein "
                f"{WOCHENTAG_NAMEN[d.weekday()]}.")

    # 2) Tage/Wochen/Monate zwischen zwei Daten
    m = re.search(r"\bzwischen\b", t)
    if m and len(daten) >= 2:
        d1, d2 = sorted(daten[:2])
        diff = (d2 - d1).days
        if "monat" in t:
            monate = (d2.year - d1.year) * 12 + (d2.month - d1.month)
            if d2.day < d1.day:
                monate -= 1
            return (f"Zwischen dem {_formatiere(d1)} und dem "
                    f"{_formatiere(d2)} liegen {monate} volle Monate.")
        if "woche" in t:
            return (f"Zwischen dem {_formatiere(d1)} und dem "
                    f"{_formatiere(d2)} liegen {diff // 7} volle Wochen "
                    f"({diff} Tage).")
        return (f"Zwischen dem {_formatiere(d1)} und dem "
                f"{_formatiere(d2)} liegen {diff} Tage.")

    # 3) N Tage/Wochen ab heute (in exakt N ...)
    m = re.search(r"\b(in|nach)\s+(exakt\s+)?(\d+)\s+(tag|tage|woche|wochen)\b",
                  t)
    if m:
        n = int(m.group(3))
        einheit = m.group(4)
        delta = n * (7 if einheit.startswith("woche") else 1)
        ziel = heute + timedelta(days=delta)
        return (f"Heute ist der {_formatiere(heute)}. "
                f"In {n} {einheit} ist das der {_formatiere(ziel)}.")

    # 4) Nächste / übernächste Woche
    if re.search(r"\b(übernächste|uebernaechste)\s+woche\b", t):
        ziel = heute + timedelta(days=14)
        return (f"Heute ist der {_formatiere(heute)}, ein "
                f"{WOCHENTAG_NAMEN[heute.weekday()]}. "
                f"Nächste Woche wäre der {_formatiere(heute + timedelta(days=7))}, "
                f"übernächste Woche der {_formatiere(ziel)}.")
    if re.search(r"\b(nächste|naechste)\s+woche\b", t):
        ziel = heute + timedelta(days=7)
        return (f"Heute ist der {_formatiere(heute)}. "
                f"Nächste Woche ist der {_formatiere(ziel)}.")

    # 5) Wie viele Tage/Wochen/Monate seit einem Datum
    if re.search(r"\b(wie\s+viele?)\s+(tage?|wochen?|monate?)\b.{0,40}?\bseit\b",
                 t) and daten:
        d = daten[0]
        diff = (heute - d).days
        if "monat" in t:
            monate = (heute.year - d.year) * 12 + (heute.month - d.month)
            if heute.day < d.day:
                monate -= 1
            return (f"Vom {_formatiere(d)} bis heute ({_formatiere(heute)}) "
                    f"sind das {monate} volle Monate.")
        if "woche" in t:
            return (f"Vom {_formatiere(d)} bis heute ({_formatiere(heute)}) "
                    f"sind {diff // 7} volle Wochen vergangen "
                    f"({diff} Tage).")
        return (f"Vom {_formatiere(d)} bis heute ({_formatiere(heute)}) "
                f"sind {diff} Tage vergangen.")

    # 6) Wie viele Wochen/Tage/Monate bis zu einem Datum
    if re.search(r"\b(wie\s+viele?)\s+(tage?|wochen?|monate?)\b.{0,40}?\b"
                 r"(bis|zu)\b", t) and daten:
        d = daten[0]
        diff = (d - heute).days
        if "monat" in t:
            monate = (d.year - heute.year) * 12 + (d.month - heute.month)
            if d.day < heute.day:
                monate -= 1
            return (f"Heute ist der {_formatiere(heute)}. "
                    f"Bis zum {_formatiere(d)} sind es {monate} volle Monate.")
        if "woche" in t:
            return (f"Heute ist der {_formatiere(heute)}. Bis zum "
                    f"{_formatiere(d)} sind es {diff // 7} volle Wochen "
                    f"({diff} Tage).")
        return (f"Heute ist der {_formatiere(heute)}. Bis zum "
                f"{_formatiere(d)} sind es {diff} Tage.")

    # Fallback — sollte selten passieren wenn ist_kalenderfrage sauber
    # klassifiziert hat. Wir geben ehrlich zurück dass der Agent
    # zwar zuständig wäre, das Muster aber nicht kennt.
    return ("Diese Kalenderfrage kann ich noch nicht deterministisch "
            "beantworten (Muster nicht erkannt). Bitte umformulieren.")


# ── Standalone ────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SUSI Datums-Agent")
    parser.add_argument("--frage", help="Einzelne Frage klassifizieren + beantworten")
    parser.add_argument("--demo", action="store_true",
                        help="10 Datumsarithmetik-Testfragen durchgehen")
    args = parser.parse_args()

    if args.frage:
        d = diagnose(args.frage)
        print(f"Frage: {args.frage}")
        print(f"  Datum/Anker vorhanden : {d['datum_oder_anker']}")
        print(f"  Kalender-Operation    : {d['kalender_operation']}")
        print(f"  Entität blockiert     : {d['entitaet'] or '—'}")
        print(f"  → Kalenderfrage?      : {d['ist_kalenderfrage']}")
        if d["ist_kalenderfrage"]:
            print()
            print("Antwort:")
            print(f"  {beantworte_kalenderfrage(args.frage)}")
        else:
            print()
            print("→ Geht an LLM+RAG-Pipeline.")
    elif args.demo:
        fragen = [
            ("datum_01", "SUSI ist seit Maerz 2026 in Betrieb. Wie alt ist sie inzwischen?"),
            ("datum_02", "Wie viele Tage sind seit dem 15. Mai 2026 bis heute vergangen?"),
            ("datum_03", "Wenn etwas in exakt 3 Wochen ab heute abläuft, zu welchem Datum ist es dann abgelaufen?"),
            ("datum_04", "Wenn ein Projekt am 1. Dezember 2025 gestartet ist, wie viele Monate laeuft es dann bis heute?"),
            ("datum_05", "Welcher Wochentag war der 31. Dezember 1999?"),
            ("datum_06", "Welcher Wochentag ist der 25. Dezember 2026?"),
            ("datum_07", "Wie viele Tage liegen zwischen dem 1. Februar 2024 und dem 1. Maerz 2024?"),
            ("datum_08", "Welches Datum ist uebernaechste Woche, gerechnet ab heute?"),
            ("datum_09", "Was liegt laenger zurueck: ein Projektstart im Januar 2026 oder ein Projektstart im Maerz 2026?"),
            ("datum_10", "Wie viele Wochen sind es noch bis Weihnachten 2026, gerechnet ab heute?"),
        ]
        py, llm = 0, 0
        for fid, f in fragen:
            d = diagnose(f)
            pfad = "PYTHON" if d["ist_kalenderfrage"] else "LLM+RAG"
            if d["ist_kalenderfrage"]:
                py += 1
            else:
                llm += 1
            print(f"\n{'='*72}")
            print(f"{fid} → {pfad}")
            print(f"  Frage: {f[:80]}")
            print(f"  Datum={d['datum_oder_anker']}, "
                  f"Op={d['kalender_operation']}, "
                  f"Entität={d['entitaet'] or '—'}")
            if d["ist_kalenderfrage"]:
                print(f"  Antwort: {beantworte_kalenderfrage(f)}")
        print(f"\n{'='*72}")
        print(f"ZUSAMMENFASSUNG: {py} Fragen → Python-Agent, "
              f"{llm} → LLM+RAG")
    else:
        parser.print_help()
        