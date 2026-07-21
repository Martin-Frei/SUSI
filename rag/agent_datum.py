"""
SUSI — agent_datum
===================
SUSI's first tool in the sense of Tool Use / Function Calling.
Detects pure calendar questions (weekday, days between, N days/weeks
from today, weeks until...) and answers them deterministically via
Python datetime, without LLM and without RAG.

Context (see docs/susi/valuecheck_und_referenz_loader.md):
    LLMs are autoregressive token predictors and structurally unreliable
    at arithmetic. The ValueCheck from 06.07.2026 makes calculation errors
    visible but doesn't fix them. The date agent is the fixing part:
    calendar questions are never presented to the LLM but calculated
    directly in Python.

Usage in rag/query.py (early, right after detect_language):
    from rag import agent_datum
    if agent_datum.is_calendar_question(question):
        return agent_datum.answer_calendar_question(question)
    # normal pipeline continues

Conservative classification — all three conditions must hold:
    1. Concrete date or date anchor in the question
       (date, "heute", "Weihnachten JJJJ", "Silvester JJJJ",
        "Martins Geburtstag" etc.)
    2. Clear calendar operation
       (weekday, days/weeks/months between, +N days/weeks,
        next/following week etc.)
    3. No SUSIpedia entity name
       (SUSI, StockPredict, GMM, HouseOfStacks, HOS, Portfolio,
        project names, mein/meine)
       Exception: explicit date in the question → entity irrelevant.
       Exception: known birthday anchor → entity irrelevant.
When in doubt → LLM+RAG. The agent only does what it can do reliably.

Standalone test:
    python rag/agent_datum.py --frage "Welcher Wochentag war der 31.12.1999?"
    python rag/agent_datum.py --demo
"""

from __future__ import annotations
import re
from datetime import date, timedelta
from typing import Optional


# ── Calendar base data ───────────────────────────────────────────
# German names required — SUSI processes and answers in German.

MONTH_NAMES = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
               "Juli", "August", "September", "Oktober", "November", "Dezember"]
WEEKDAY_NAMES = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
                 "Freitag", "Samstag", "Sonntag"]

MONTH_TO_NUM = {n.lower(): i for i, n in enumerate(MONTH_NAMES) if n}
MONTH_TO_NUM.update({"märz": 3, "maerz": 3})

# Fixed calendar anchors — date is unambiguous.
# Person birthdays go here so _parse_date() can find them.
ANCHOR_DAY_MONTH: dict[str, tuple[int, int]] = {
    "weihnachten":       (25, 12),
    "heiligabend":       (24, 12),
    "silvester":         (31, 12),
    "neujahr":           (1,  1),
    # Person birthdays (hard-coded, deterministically known)
    "martin geburtstag": (29, 11),
    "martins geburtstag":(29, 11),
}

# Birthday phrases as separate regex — multi-word keys like
# "martin geburtstag" can't be matched via \b word boundary
# in a simple DATE_PATTERNS entry.
BIRTHDAY_PATTERN = re.compile(
    r"\b(martins?)\s+geburtstag\b", re.IGNORECASE
)


# ── SUSIpedia entities (block list for condition 3) ───────────────

ENTITIES = {
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


# ── Branch 2 — duration whitelist ─────────────────────────────────

DURATION_ENTITIES: dict[str, str] = {
    "susi":          "projekt",
    "stockpredict":  "projekt",
    "spv2":          "projekt",
    "gmm":           "projekt",
    "houseofstacks": "projekt",
    "hos":           "projekt",
    "martin":        "person",
    "philip":        "person",    
    "jakob":         "person",
    "adeena":        "person",
    "tanveer":       "person",
}

DURATION_PATTERNS = [
    re.compile(r"\bwie\s+alt\b",   re.IGNORECASE),
    re.compile(r"\bseit\s+wann\b", re.IGNORECASE),
    re.compile(r"\bwie\s+lange\b", re.IGNORECASE),
    re.compile(r"\bwie\s*viele?\s+(monate?|jahre?)\b", re.IGNORECASE),
]

# SUSIpedia metadata lines that are not content dates.
CHUNK_FILTER_PATTERNS = [
    re.compile(r"^Datum:[^\n]*\n?", flags=re.MULTILINE),
    re.compile(r"##\s*\*\*Stand[^\n]*\n?"),
]


# ── Condition 1 — date detection ─────────────────────────────────

DATE_PATTERNS = [
    re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b"),
    re.compile(r"\b(\d{1,2})\.\s*("
               + "|".join(MONTH_TO_NUM.keys())
               + r")\s+(\d{4})\b", re.IGNORECASE),
    re.compile(r"\b(" + "|".join(re.escape(k) for k in ANCHOR_DAY_MONTH.keys())
               + r")\s+(\d{4})\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,2})\.\s*(" + "|".join(MONTH_TO_NUM.keys()) + r")\b",
               re.IGNORECASE),
    re.compile(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.(?!\d)"),
]

TODAY_PATTERN = re.compile(r"\b(heute|jetzt|aktuell)\b", re.IGNORECASE)


def _has_date_or_anchor(text: str) -> bool:
    if TODAY_PATTERN.search(text):
        return True
    if BIRTHDAY_PATTERN.search(text):
        return True
    return any(m.search(text) for m in DATE_PATTERNS)


# ── Condition 2 — calendar operation ─────────────────────────────

OPERATION_PATTERNS = [
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
    re.compile(r"\b(bis\s+zu[mr]?)\b.{0,30}?\bgeburtstag\b", re.IGNORECASE),
]


def _has_calendar_operation(text: str) -> bool:
    return any(m.search(text) for m in OPERATION_PATTERNS)


# ── Condition 3 — no SUSIpedia entity ────────────────────────────

def _has_entity(text: str) -> Optional[str]:
    if any(m.search(text) for m in DATE_PATTERNS):
        return None
    if BIRTHDAY_PATTERN.search(text):
        return None
    t = text.lower()
    for e in ENTITIES:
        if re.search(rf"\b{re.escape(e)}\b", t):
            return e
    return None


# ── Public API — classification ──────────────────────────────────

def is_calendar_question(text: str) -> bool:
    if not text or len(text) > 500:
        return False
    if not _has_date_or_anchor(text):
        return False
    if not _has_calendar_operation(text):
        return False
    if _has_entity(text) is not None:
        return False
    return True


def diagnose(text: str) -> dict:
    return {
        "date_or_anchor": _has_date_or_anchor(text),
        "calendar_operation": _has_calendar_operation(text),
        "entity": _has_entity(text),
        "is_calendar_question": is_calendar_question(text),
    }


# ── Date parser ───────────────────────────────────────────────────

def _parse_date(text: str) -> list[date]:
    matches: list[date] = []

    for m in re.finditer(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", text):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= d <= 31 and 1 <= mo <= 12:
            try:
                matches.append(date(y, mo, d))
            except ValueError:
                pass

    for m in re.finditer(
        r"\b(\d{1,2})\.\s*(" + "|".join(MONTH_TO_NUM.keys()) + r")\s+(\d{4})\b",
        text, re.IGNORECASE
    ):
        d, mo, y = int(m.group(1)), MONTH_TO_NUM[m.group(2).lower()], int(m.group(3))
        try:
            matches.append(date(y, mo, d))
        except ValueError:
            pass

    for m in re.finditer(
        r"\b(" + "|".join(re.escape(k) for k in ANCHOR_DAY_MONTH.keys())
        + r")\s+(\d{4})\b", text, re.IGNORECASE
    ):
        d, mo = ANCHOR_DAY_MONTH[m.group(1).lower()]
        y = int(m.group(2))
        try:
            matches.append(date(y, mo, d))
        except ValueError:
            pass

    if BIRTHDAY_PATTERN.search(text):
        key = "martins geburtstag"
        tag, monat = ANCHOR_DAY_MONTH[key]
        y = date.today().year
        try:
            candidate = date(y, monat, tag)
            if candidate < date.today():
                candidate = date(y + 1, monat, tag)
            if not any(t.day == tag and t.month == monat for t in matches):
                matches.append(candidate)
        except ValueError:
            pass

    for m in re.finditer(
        r"\b(\d{1,2})\.\s*(" + "|".join(MONTH_TO_NUM.keys()) + r")\b",
        text, re.IGNORECASE
    ):
        d, mo = int(m.group(1)), MONTH_TO_NUM[m.group(2).lower()]
        if any(t.day == d and t.month == mo for t in matches):
            continue
        y = date.today().year
        try:
            candidate = date(y, mo, d)
            if candidate < date.today():
                candidate = date(y + 1, mo, d)
            matches.append(candidate)
        except ValueError:
            pass

    for m in re.finditer(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.(?!\d)", text):
        d, mo = int(m.group(1)), int(m.group(2))
        if 1 <= d <= 31 and 1 <= mo <= 12:
            if any(t.day == d and t.month == mo for t in matches):
                continue
            y = date.today().year
            try:
                candidate = date(y, mo, d)
                if candidate < date.today():
                    candidate = date(y + 1, mo, d)
                matches.append(candidate)
            except ValueError:
                pass

    return matches


def _format_date(d: date) -> str:
    return f"{d.day}. {MONTH_NAMES[d.month]} {d.year}"


def _format_date_short(d: date) -> str:
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


# ── Public API — execution ────────────────────────────────────────

def answer_calendar_question(text: str, today: Optional[date] = None) -> str:
    if today is None:
        today = date.today()

    dates = _parse_date(text)
    t = text.lower()

    # 1) Weekday
    if re.search(r"\bwochentag\b", t) and dates:
        d = dates[0]
        verb = "war" if d < today else "ist"
        return f"Der {_format_date(d)} {verb} ein {WEEKDAY_NAMES[d.weekday()]}."

    # 2) Between two dates
    if re.search(r"\bzwischen\b", t) and len(dates) >= 2:
        d1, d2 = sorted(dates[:2])
        diff = (d2 - d1).days
        if "monat" in t:
            months = (d2.year - d1.year) * 12 + (d2.month - d1.month)
            if d2.day < d1.day:
                months -= 1
            return (f"Zwischen dem {_format_date(d1)} und dem "
                    f"{_format_date(d2)} liegen {months} volle Monate.")
        if "woche" in t:
            return (f"Zwischen dem {_format_date(d1)} und dem "
                    f"{_format_date(d2)} liegen {diff // 7} volle Wochen ({diff} Tage).")
        return f"Zwischen dem {_format_date(d1)} und dem {_format_date(d2)} liegen {diff} Tage."

    # 3) In N days/weeks
    m = re.search(r"\b(in|nach)\s+(exakt\s+)?(\d+)\s+(tag|tage|woche|wochen)\b", t)
    if m:
        n = int(m.group(3))
        unit = m.group(4)
        target = today + timedelta(days=n * (7 if unit.startswith("woche") else 1))
        return f"Heute ist der {_format_date(today)}. In {n} {unit} ist das der {_format_date(target)}."

    # 4) Next / following week
    if re.search(r"\b(übernächste|uebernaechste)\s+woche\b", t):
        return (f"Heute ist der {_format_date(today)}, ein {WEEKDAY_NAMES[today.weekday()]}. "
                f"Nächste Woche wäre der {_format_date(today + timedelta(days=7))}, "
                f"übernächste Woche der {_format_date(today + timedelta(days=14))}.")
    if re.search(r"\b(nächste|naechste)\s+woche\b", t):
        return (f"Heute ist der {_format_date(today)}. "
                f"Nächste Woche ist der {_format_date(today + timedelta(days=7))}.")

    # 5) Since a date
    if re.search(r"\b(wie\s*viele?)\s+(tage?|wochen?|monate?)\b.{0,40}?\bseit\b", t) and dates:
        d = dates[0]
        diff = (today - d).days
        if "monat" in t:
            months = (today.year - d.year) * 12 + (today.month - d.month)
            if today.day < d.day:
                months -= 1
            return f"Vom {_format_date(d)} bis heute ({_format_date(today)}) sind das {months} volle Monate."
        if "woche" in t:
            return (f"Vom {_format_date(d)} bis heute ({_format_date(today)}) "
                    f"sind {diff // 7} volle Wochen vergangen ({diff} Tage).")
        return f"Vom {_format_date(d)} bis heute ({_format_date(today)}) sind {diff} Tage vergangen."

    # 6) Until a date (incl. birthday)
    if (re.search(r"\b(wie\s*viele?)\s+(tage?|wochen?|monate?)\b.{0,40}?\b(bis|zu)\b", t)
            or re.search(r"\b(bis\s+zu[mr]?)\b.{0,30}?\bgeburtstag\b", t)) and dates:
        d = dates[0]
        diff = (d - today).days
        if "monat" in t:
            months = (d.year - today.year) * 12 + (d.month - today.month)
            if d.day < today.day:
                months -= 1
            return f"Heute ist der {_format_date(today)}. Bis zum {_format_date(d)} sind es {months} volle Monate."
        if "woche" in t:
            return (f"Heute ist der {_format_date(today)}. Bis zum "
                    f"{_format_date(d)} sind es {diff // 7} volle Wochen ({diff} Tage).")
        return f"Heute ist der {_format_date(today)}. Bis zum {_format_date(d)} sind es {diff} Tage."

    return ("Diese Kalenderfrage kann ich noch nicht deterministisch "
            "beantworten (Muster nicht erkannt). Bitte umformulieren.")


# ── Branch 2 — public API ─────────────────────────────────────────

def is_duration_question(text: str) -> Optional[str]:
    if not text or len(text) > 500:
        return None
    if not any(m.search(text) for m in DURATION_PATTERNS):
        return None
    t = text.lower()
    # 1. Bekannte Entity aus Whitelist (exakter Typ bekannt)
    for e in DURATION_ENTITIES:
        if re.search(rf"\b{re.escape(e)}\b", t):
            return e
    # 2. Generisch: Name aus Frage extrahieren (Fallback-Typ: person)
    m = re.search(r"\bwie\s+alt\s+ist\s+(\w+)", t)
    if m:
        return m.group(1)
    m = re.search(r"\bseit\s+wann\s+(?:gibt\s+es|läuft|existiert)\s+(\w+)", t)
    if m:
        return m.group(1)
    return None


def calculate_duration_from_chunk(question: str, chunk: str,
                                   today: Optional[date] = None,
                                   entity_name: Optional[str] = None) -> Optional[str]:
    """Extracts the start date from the chunk and calculates the difference
    to today deterministically. Returns None if no date found.

    Args:
        question:    Original question (used for unit detection: "monat" etc.)
        chunk:       RAG chunk text to extract date from
        today:       Override for today's date (for testing)
        entity_name: Entity name from is_duration_question(), passed from
                     query.py to avoid re-detection on typo'd original question.

    Strategy: If the chunk has multiple ## sections, find the section
    containing the entity name and parse dates only from that section.
    This prevents picking Philip's birthday when asking about Jakob
    (both in the same chunk). Falls back to full-chunk parsing if
    no section matches.
    """
    if today is None:
        today = date.today()

    entity = entity_name or is_duration_question(question) or "die genannte Entität"
    entity_type = DURATION_ENTITIES.get(entity, "person")

    chunk_clean = chunk
    for f in CHUNK_FILTER_PATTERNS:
        chunk_clean = f.sub("", chunk_clean)

    # Try entity-scoped section first (## heading boundaries)
    sections = re.split(r"(?=^## )", chunk_clean, flags=re.MULTILINE)
    entity_section = None
    for section in sections:
        if entity.lower() in section.lower():
            entity_section = section
            break

    # Parse dates from entity section, fall back to full chunk
    dates = _parse_date(entity_section) if entity_section else _parse_date(chunk_clean)
    if not dates and entity_section:
        # Section had no parseable dates, try full chunk as fallback
        dates = _parse_date(chunk_clean)
    if not dates:
        return None

    past_dates = [d for d in dates if d <= today]
    if not past_dates:
        return None
    d = min(past_dates)

    diff_days   = (today - d).days
    diff_months = (today.year - d.year) * 12 + (today.month - d.month)
    if today.day < d.day:
        diff_months -= 1
    diff_years  = diff_months // 12
    rest_months = diff_months % 12

    t = question.lower()

    if entity_type == "person":
        fact = (f"{diff_months} Monate ({diff_years} Jahre und {rest_months} Monate)"
                if "monat" in t else f"{diff_years} Jahre alt")
        return (f"HINWEIS: Die folgende Angabe wurde deterministisch berechnet und ist korrekt. "
                f"{entity} wurde am {_format_date(d)} geboren, das sind heute {fact}. "
                f"Verwende diese Angabe in deiner Antwort.")
    else:
        fact = (f"{diff_years} Jahre und {rest_months} Monate"
                if diff_months >= 24 else f"{diff_months} Monate")
        return (f"HINWEIS: Die folgende Angabe wurde deterministisch berechnet und ist korrekt. "
                f"{entity} läuft seit {_format_date(d)}, das sind heute {fact} "
                f"({diff_days} Tage). Verwende diese Angabe in deiner Antwort.")


# ── Standalone ────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SUSI date agent")
    parser.add_argument("--frage", help="Classify + answer a single question")
    parser.add_argument("--demo", action="store_true",
                        help="Run 10 date arithmetic test questions")
    args = parser.parse_args()

    if args.frage:
        d = diagnose(args.frage)
        print(f"Frage: {args.frage}")
        print(f"  Datum/Anker vorhanden : {d['date_or_anchor']}")
        print(f"  Kalender-Operation    : {d['calendar_operation']}")
        print(f"  Entität blockiert     : {d['entity'] or '—'}")
        print(f"  → Kalenderfrage?      : {d['is_calendar_question']}")
        if d["is_calendar_question"]:
            print(f"\nAntwort:\n  {answer_calendar_question(args.frage)}")
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
            path = "PYTHON" if d["is_calendar_question"] else "LLM+RAG"
            if d["is_calendar_question"]:
                py += 1
            else:
                llm += 1
            print(f"\n{'='*72}")
            print(f"{fid} → {path}")
            print(f"  Frage: {f[:80]}")
            print(f"  Date={d['date_or_anchor']}, Op={d['calendar_operation']}, Entity={d['entity'] or '—'}")
            if d["is_calendar_question"]:
                print(f"  Antwort: {answer_calendar_question(f)}")
        print(f"\n{'='*72}")
        print(f"SUMMARY: {py} questions → Python agent, {llm} → LLM+RAG")
    else:
        parser.print_help()