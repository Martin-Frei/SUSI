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
    from rag import agent_datum
    if agent_datum.ist_kalenderfrage(frage):
        return agent_datum.beantworte_kalenderfrage(frage)
    # ab hier normale Pipeline

Konservative Klassifikation — alle drei Bedingungen müssen gelten:
    1. Konkretes Datum oder Datums-Anker in der Frage
       (Datum, "heute", "Weihnachten JJJJ", "Silvester JJJJ",
        "Martins Geburtstag" usw.)
    2. Klare Kalender-Operation
       (Wochentag, Tage/Wochen/Monate zwischen, +N Tage/Wochen,
        übernächste Woche etc.)
    3. Kein SUSIpedia-Entitätsname
       (SUSI, StockPredict, GMM, HouseOfStacks, HOS, Portfolio,
        Projekt-Namen, mein/meine)
       Ausnahme: explizites Datum in der Frage → Entität irrelevant.
       Ausnahme: bekannter Geburtstags-Anker → Entität irrelevant.
Im Zweifel → LLM+RAG. Der Agent macht nur was er sicher kann.

Standalone-Test:
    python rag/agent_datum.py --frage "Welcher Wochentag war der 31.12.1999?"
    python rag/agent_datum.py --demo    # Klassifikation der 10 Testfragen
"""

from __future__ import annotations
import re
from datetime import date, timedelta
from typing import Optional


# ── Kalender-Grunddaten ──────────────────────────────────────────

MONATE_NAMEN = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
                "Juli", "August", "September", "Oktober", "November", "Dezember"]
WOCHENTAG_NAMEN = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
                   "Freitag", "Samstag", "Sonntag"]

MONAT_ZU_NUM = {n.lower(): i for i, n in enumerate(MONATE_NAMEN) if n}
MONAT_ZU_NUM.update({"märz": 3, "maerz": 3})

# Feste Kalender-Anker — Datum liegt eindeutig fest.
# Personen-Geburtstage hier eintragen damit _parse_datum() sie findet.
ANKER_TAG_MONAT: dict[str, tuple[int, int]] = {
    "weihnachten":       (25, 12),
    "heiligabend":       (24, 12),
    "silvester":         (31, 12),
    "neujahr":           (1,  1),
    # Personen-Geburtstage (hard-coded, da deterministisch bekannt)
    "martin geburtstag": (29, 11),
    "martins geburtstag":(29, 11),
}

# Geburtstags-Phrasen als eigenes Regex — Mehrteilige Schlüssel wie
# "martin geburtstag" können nicht per \b-Wortgrenze in einem
# einfachen DATUM_MUSTER erkannt werden.
GEBURTSTAG_MUSTER = re.compile(
    r"\b(martins?)\s+geburtstag\b", re.IGNORECASE
)


# ── SUSIpedia-Entitäten (Sperrliste Bedingung 3) ─────────────────

ENTITAETEN = {
    "susi", "stockpredict", "spv2", "sp v2",
    "gmm", "global market mood",
    "houseofstacks", "house of stacks", "hos",
    "portfolio", "portfolio_site",
    "martin", "tanveer", "adeena",
    "mein", "meine", "meinen", "meines", "meiner",
    "ich", "mir", "mich",
    "projekt", "projekts", "projekte",
    "firma", "team", "kollege", "kollegen",
}


# ── Zweig 2 — Laufzeit-Whitelist ─────────────────────────────────

LAUFZEIT_ENTITAETEN: dict[str, str] = {
    "susi":          "projekt",
    "stockpredict":  "projekt",
    "spv2":          "projekt",
    "gmm":           "projekt",
    "houseofstacks": "projekt",
    "hos":           "projekt",
    "martin":        "person",
    "jakob":         "person",
    "adeena":        "person",
    "tanveer":       "person",
}

DAUER_MUSTER = [
    re.compile(r"\bwie\s+alt\b",   re.IGNORECASE),
    re.compile(r"\bseit\s+wann\b", re.IGNORECASE),
    re.compile(r"\bwie\s+lange\b", re.IGNORECASE),
    re.compile(r"\bwie\s*viele?\s+(monate?|jahre?)\b", re.IGNORECASE),
]

# SUSIpedia-Metadaten-Zeilen die keine inhaltlichen Startdaten sind.
CHUNK_FILTER_MUSTER = [
    re.compile(r"^Datum:[^\n]*\n?", flags=re.MULTILINE),
    re.compile(r"##\s*\*\*Stand[^\n]*\n?"),
]


# ── Bedingung 1 — Datums-Erkennung ───────────────────────────────

DATUM_MUSTER = [
    re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b"),
    re.compile(r"\b(\d{1,2})\.\s*("
               + "|".join(MONAT_ZU_NUM.keys())
               + r")\s+(\d{4})\b", re.IGNORECASE),
    re.compile(r"\b(" + "|".join(re.escape(k) for k in ANKER_TAG_MONAT.keys())
               + r")\s+(\d{4})\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,2})\.\s*(" + "|".join(MONAT_ZU_NUM.keys()) + r")\b",
               re.IGNORECASE),
    re.compile(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.(?!\d)"),
]

HEUTE_MUSTER = re.compile(r"\b(heute|jetzt|aktuell)\b", re.IGNORECASE)


def _hat_datum_oder_anker(text: str) -> bool:
    if HEUTE_MUSTER.search(text):
        return True
    if GEBURTSTAG_MUSTER.search(text):
        return True
    return any(m.search(text) for m in DATUM_MUSTER)


# ── Bedingung 2 — Kalender-Operation ─────────────────────────────

OPERATION_MUSTER = [
    re.compile(r"\bwelcher\s+wochentag\b", re.IGNORECASE),
    re.compile(r"\bwochentag\s+(war|ist|fällt|fiel)\b", re.IGNORECASE),
    re.compile(r"\bwie\s*viele?\s+tage?\b.{0,40}?\b(seit|bis|zwischen|zw\.)\b",
               re.IGNORECASE),
    re.compile(r"\bwie\s*viele?\s+wochen?\b.{0,40}?\b(seit|bis|zwischen|zw\.|noch)\b",
               re.IGNORECASE),
    re.compile(r"\bwie\s*viele?\s+monate?\b.{0,40}?\b(seit|bis|zwischen|zw\.)\b",
               re.IGNORECASE),
    re.compile(r"\b(in|nach)\s+(exakt\s+)?\d+\s+(tag|tage|woche|wochen)\b",
               re.IGNORECASE),
    re.compile(r"\b(nächste|übernächste|naechste|uebernaechste)\s+woche\b",
               re.IGNORECASE),
    re.compile(r"\bab\s+heute\b", re.IGNORECASE),
    # Geburtstags-Fragen: "wieviele Tage bis zu Martins Geburtstag"
    re.compile(r"\b(bis\s+zu[mr]?)\b.{0,30}?\bgeburtstag\b", re.IGNORECASE),
]


def _hat_kalender_operation(text: str) -> bool:
    return any(m.search(text) for m in OPERATION_MUSTER)


# ── Bedingung 3 — Keine SUSIpedia-Entität ────────────────────────

def _hat_entitaet(text: str) -> Optional[str]:
    # Explizites Datum → Entität egal
    if any(m.search(text) for m in DATUM_MUSTER):
        return None
    # Bekannter Geburtstags-Anker → Entität egal
    if GEBURTSTAG_MUSTER.search(text):
        return None
    t = text.lower()
    for e in ENTITAETEN:
        if re.search(rf"\b{re.escape(e)}\b", t):
            return e
    return None


# ── öffentliche API — Klassifikation ─────────────────────────────

def ist_kalenderfrage(text: str) -> bool:
    if not text or len(text) > 500:
        return False
    if not _hat_datum_oder_anker(text):
        return False
    if not _hat_kalender_operation(text):
        return False
    if _hat_entitaet(text) is not None:
        return False
    return True


def diagnose(text: str) -> dict:
    return {
        "datum_oder_anker": _hat_datum_oder_anker(text),
        "kalender_operation": _hat_kalender_operation(text),
        "entitaet": _hat_entitaet(text),
        "ist_kalenderfrage": ist_kalenderfrage(text),
    }


# ── Datums-Parser ─────────────────────────────────────────────────

def _parse_datum(text: str) -> list[date]:
    treffer: list[date] = []

    # Numerisch mit Jahr: 25.12.2026
    for m in re.finditer(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", text):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= d <= 31 and 1 <= mo <= 12:
            try:
                treffer.append(date(y, mo, d))
            except ValueError:
                pass

    # Wörtlich mit Jahr: "31. Dezember 1999"
    for m in re.finditer(
        r"\b(\d{1,2})\.\s*(" + "|".join(MONAT_ZU_NUM.keys()) + r")\s+(\d{4})\b",
        text, re.IGNORECASE
    ):
        d, mo, y = int(m.group(1)), MONAT_ZU_NUM[m.group(2).lower()], int(m.group(3))
        try:
            treffer.append(date(y, mo, d))
        except ValueError:
            pass

    # Anker mit Jahr: "Weihnachten 2026"
    for m in re.finditer(
        r"\b(" + "|".join(re.escape(k) for k in ANKER_TAG_MONAT.keys())
        + r")\s+(\d{4})\b", text, re.IGNORECASE
    ):
        d, mo = ANKER_TAG_MONAT[m.group(1).lower()]
        y = int(m.group(2))
        try:
            treffer.append(date(y, mo, d))
        except ValueError:
            pass

    # Geburtstags-Anker ohne Jahr → nächstes Vorkommen
    if GEBURTSTAG_MUSTER.search(text):
        key = "martins geburtstag"
        tag, monat = ANKER_TAG_MONAT[key]
        y = date.today().year
        try:
            candidate = date(y, monat, tag)
            if candidate < date.today():
                candidate = date(y + 1, monat, tag)
            if not any(t.day == tag and t.month == monat for t in treffer):
                treffer.append(candidate)
        except ValueError:
            pass

    # Wörtlich ohne Jahr: "29. November" → nächstes Vorkommen
    for m in re.finditer(
        r"\b(\d{1,2})\.\s*(" + "|".join(MONAT_ZU_NUM.keys()) + r")\b",
        text, re.IGNORECASE
    ):
        d, mo = int(m.group(1)), MONAT_ZU_NUM[m.group(2).lower()]
        if any(t.day == d and t.month == mo for t in treffer):
            continue
        y = date.today().year
        try:
            candidate = date(y, mo, d)
            if candidate < date.today():
                candidate = date(y + 1, mo, d)
            treffer.append(candidate)
        except ValueError:
            pass

    # Numerisch ohne Jahr: "29.11."
    for m in re.finditer(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.(?!\d)", text):
        d, mo = int(m.group(1)), int(m.group(2))
        if 1 <= d <= 31 and 1 <= mo <= 12:
            if any(t.day == d and t.month == mo for t in treffer):
                continue
            y = date.today().year
            try:
                candidate = date(y, mo, d)
                if candidate < date.today():
                    candidate = date(y + 1, mo, d)
                treffer.append(candidate)
            except ValueError:
                pass

    return treffer


def _formatiere(d: date) -> str:
    return f"{d.day}. {MONATE_NAMEN[d.month]} {d.year}"


def _formatiere_kurz(d: date) -> str:
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


# ── öffentliche API — Ausführung ──────────────────────────────────

def beantworte_kalenderfrage(text: str, heute: Optional[date] = None) -> str:
    if heute is None:
        heute = date.today()

    daten = _parse_datum(text)
    t = text.lower()

    # 1) Wochentag
    if re.search(r"\bwochentag\b", t) and daten:
        d = daten[0]
        verb = "war" if d < heute else "ist"
        return f"Der {_formatiere(d)} {verb} ein {WOCHENTAG_NAMEN[d.weekday()]}."

    # 2) Zwischen zwei Daten
    if re.search(r"\bzwischen\b", t) and len(daten) >= 2:
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
                    f"{_formatiere(d2)} liegen {diff // 7} volle Wochen ({diff} Tage).")
        return f"Zwischen dem {_formatiere(d1)} und dem {_formatiere(d2)} liegen {diff} Tage."

    # 3) In N Tage/Wochen
    m = re.search(r"\b(in|nach)\s+(exakt\s+)?(\d+)\s+(tag|tage|woche|wochen)\b", t)
    if m:
        n = int(m.group(3))
        einheit = m.group(4)
        ziel = heute + timedelta(days=n * (7 if einheit.startswith("woche") else 1))
        return f"Heute ist der {_formatiere(heute)}. In {n} {einheit} ist das der {_formatiere(ziel)}."

    # 4) Nächste / übernächste Woche
    if re.search(r"\b(übernächste|uebernaechste)\s+woche\b", t):
        return (f"Heute ist der {_formatiere(heute)}, ein {WOCHENTAG_NAMEN[heute.weekday()]}. "
                f"Nächste Woche wäre der {_formatiere(heute + timedelta(days=7))}, "
                f"übernächste Woche der {_formatiere(heute + timedelta(days=14))}.")
    if re.search(r"\b(nächste|naechste)\s+woche\b", t):
        return (f"Heute ist der {_formatiere(heute)}. "
                f"Nächste Woche ist der {_formatiere(heute + timedelta(days=7))}.")

    # 5) Seit einem Datum
    if re.search(r"\b(wie\s*viele?)\s+(tage?|wochen?|monate?)\b.{0,40}?\bseit\b", t) and daten:
        d = daten[0]
        diff = (heute - d).days
        if "monat" in t:
            monate = (heute.year - d.year) * 12 + (heute.month - d.month)
            if heute.day < d.day:
                monate -= 1
            return f"Vom {_formatiere(d)} bis heute ({_formatiere(heute)}) sind das {monate} volle Monate."
        if "woche" in t:
            return (f"Vom {_formatiere(d)} bis heute ({_formatiere(heute)}) "
                    f"sind {diff // 7} volle Wochen vergangen ({diff} Tage).")
        return f"Vom {_formatiere(d)} bis heute ({_formatiere(heute)}) sind {diff} Tage vergangen."

    # 6) Bis zu einem Datum (inkl. Geburtstag)
    if (re.search(r"\b(wie\s*viele?)\s+(tage?|wochen?|monate?)\b.{0,40}?\b(bis|zu)\b", t)
            or re.search(r"\b(bis\s+zu[mr]?)\b.{0,30}?\bgeburtstag\b", t)) and daten:
        d = daten[0]
        diff = (d - heute).days
        if "monat" in t:
            monate = (d.year - heute.year) * 12 + (d.month - heute.month)
            if d.day < heute.day:
                monate -= 1
            return f"Heute ist der {_formatiere(heute)}. Bis zum {_formatiere(d)} sind es {monate} volle Monate."
        if "woche" in t:
            return (f"Heute ist der {_formatiere(heute)}. Bis zum "
                    f"{_formatiere(d)} sind es {diff // 7} volle Wochen ({diff} Tage).")
        return f"Heute ist der {_formatiere(heute)}. Bis zum {_formatiere(d)} sind es {diff} Tage."

    return ("Diese Kalenderfrage kann ich noch nicht deterministisch "
            "beantworten (Muster nicht erkannt). Bitte umformulieren.")


# ── Zweig 2 — öffentliche API ─────────────────────────────────────

def ist_laufzeitfrage(text: str) -> Optional[str]:
    if not text or len(text) > 500:
        return None
    if not any(m.search(text) for m in DAUER_MUSTER):
        return None
    t = text.lower()
    for e in LAUFZEIT_ENTITAETEN:
        if re.search(rf"\b{re.escape(e)}\b", t):
            return e
    return None


def berechne_laufzeit_aus_chunk(frage: str, chunk: str,
                                 heute: Optional[date] = None) -> Optional[str]:
    """Extrahiert das Startdatum aus dem Chunk und berechnet die Differenz
    zu heute deterministisch. Gibt None zurück wenn kein Datum gefunden."""
    if heute is None:
        heute = date.today()

    chunk_clean = chunk
    for f in CHUNK_FILTER_MUSTER:
        chunk_clean = f.sub("", chunk_clean)

    daten = _parse_datum(chunk_clean)
    if not daten:
        return None

    daten_vergangen = [d for d in daten if d <= heute]
    if not daten_vergangen:
        return None
    d = min(daten_vergangen)

    diff_tage   = (heute - d).days
    diff_monate = (heute.year - d.year) * 12 + (heute.month - d.month)
    if heute.day < d.day:
        diff_monate -= 1
    diff_jahre  = diff_monate // 12
    rest_monate = diff_monate % 12

    entitaet = ist_laufzeitfrage(frage) or "die genannte Entität"
    typ       = LAUFZEIT_ENTITAETEN.get(entitaet, "projekt")
    t         = frage.lower()

    if typ == "person":
        fakt = (f"{diff_monate} Monate ({diff_jahre} Jahre und {rest_monate} Monate)"
                if "monat" in t else f"{diff_jahre} Jahre alt")
        return (f"HINWEIS: Die folgende Angabe wurde deterministisch berechnet und ist korrekt. "
                f"{entitaet} wurde am {_formatiere(d)} geboren, das sind heute {fakt}. "
                f"Verwende diese Angabe in deiner Antwort.")
    else:
        fakt = (f"{diff_jahre} Jahre und {rest_monate} Monate"
                if diff_monate >= 24 else f"{diff_monate} Monate")
        return (f"HINWEIS: Die folgende Angabe wurde deterministisch berechnet und ist korrekt. "
                f"{entitaet} läuft seit {_formatiere(d)}, das sind heute {fakt} "
                f"({diff_tage} Tage). Verwende diese Angabe in deiner Antwort.")


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
            print(f"\nAntwort:\n  {beantworte_kalenderfrage(args.frage)}")
        else:
            print("\n→ Geht an LLM+RAG-Pipeline.")
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
            print(f"  Datum={d['datum_oder_anker']}, Op={d['kalender_operation']}, Entität={d['entitaet'] or '—'}")
            if d["ist_kalenderfrage"]:
                print(f"  Antwort: {beantworte_kalenderfrage(f)}")
        print(f"\n{'='*72}")
        print(f"ZUSAMMENFASSUNG: {py} Fragen → Python-Agent, {llm} → LLM+RAG")
    else:
        parser.print_help()