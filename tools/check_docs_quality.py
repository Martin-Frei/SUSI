"""
check_docs_quality.py
=====================
Analysiert alle Markdown-Dateien in der SUSIpedia auf RAG-Retrieval-Qualität.

HINTERGRUND:
    nomic-embed-text (das Embedding-Modell von SUSI) erzeugt Vektoren aus Text-Chunks.
    Tabellen, Codeblöcke und reine Listen produzieren bedeutungslose Vektoren –
    ChromaDB findet diese Chunks dann nicht wenn SUSI eine Frage stellt.
    Dieses Script identifiziert Dateien die überarbeitet werden müssen.

    Kommentar-Blöcke (##** ... **##) werden vor der Analyse entfernt –
    genau wie ingest.py sie beim Indexieren überspringt.

    Der Abschnitt vor dem ersten ## Header (Datei-Header mit Datum/Status)
    wird beim Check ignoriert da er kein inhaltlicher Abschnitt ist.

WAS WIRD GECHECKT:
    1. Tabellen ohne Prosa-Einleitung
    2. Codeblöcke ohne Prosa-Einleitung
    3. Abschnitte die nur aus Listen bestehen
    4. Zu kurze Abschnitte (unter MIN_SECTION_CHARS Zeichen Prosa)
    5. Zu niedriger Prosa-Anteil pro Datei (unter MIN_PROSE_RATIO)

STELLSCHRAUBEN:
    DOCS_PATH         → Pfad zur SUSIpedia (relativ zum Projektroot)
    REPORT_PATH       → Pfad zur Ausgabedatei (wird immer überschrieben)
    MIN_SECTION_CHARS → Minimale Zeichenanzahl pro ## Abschnitt
    MIN_PROSE_RATIO   → Minimaler Anteil Prosa-Zeilen pro Datei (0.0 - 1.0)
    LIST_RATIO        → Ab welchem Listen-Anteil wird gewarnt (0.0 - 1.0)
    MIN_PROSE_BEFORE  → Minimale Prosa-Zeichen vor Tabelle/Codeblock
    COMMENT_START     → Öffnungs-Tag für Kommentar-Blöcke (wie in ingest.py)
    COMMENT_END       → Schließ-Tag für Kommentar-Blöcke (wie in ingest.py)

AUSGABE:
    Konsole                  → nur Zusammenfassung
    tools/quality_report.md  → alle Details, wird immer überschrieben

AUSFÜHREN:
    python tools/check_docs_quality.py
"""

from pathlib import Path
import re

# ── Stellschrauben ────────────────────────────────────────────────────────────

DOCS_PATH   = "docs"
REPORT_PATH = "tools/quality_report.md"

MIN_SECTION_CHARS = 80
MIN_PROSE_RATIO   = 0.30
LIST_RATIO        = 0.50
MIN_PROSE_BEFORE  = 30

COMMENT_START = "##**"
COMMENT_END   = "**##"

# Datei-Header Abschnitt — wird beim Check ignoriert
HEADER_SECTION = "__(Vor erstem Header)__"

# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def remove_comment_blocks(text: str) -> str:
    """Entfernt alle ##** ... **## Kommentar-Blöcke vor der Analyse."""
    pattern = re.escape(COMMENT_START) + r".*?" + re.escape(COMMENT_END)
    cleaned = re.sub(pattern, "", text, flags=re.DOTALL)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def is_prose_line(line: str) -> bool:
    """
    Prüft ob eine Zeile echter Prosa-Text ist.
    Datei-Header Zeilen wie **Datum:** und **Status:** gelten als Prosa.
    """
    s = line.strip()
    if not s:
        return False
    if s.startswith("#"):
        return False
    # Datei-Header Zeilen sind Prosa
    if s.startswith("**") and ":**" in s:
        return True
    if s.startswith(("-", "*", "+")):
        return False
    if s.startswith("|"):
        return False
    if s.startswith("```"):
        return False
    if s.startswith("    ") or s.startswith("\t"):
        return False
    if s.startswith("---") or s.startswith("==="):
        return False
    if s.startswith(">"):
        return False
    return True


def get_prose_before(lines: list, index: int) -> str:
    """
    Gibt Prosa-Text zurück der direkt vor Zeile index steht.
    Leerzeilen werden übersprungen — eine Leerzeile zwischen
    Einleitung und Codeblock ist guter Stil und kein Fehler.
    """
    prose = []
    for i in range(index - 1, max(index - 8, -1), -1):
        line = lines[i].strip()
        if line.startswith("#"):
            break
        if not line:
            continue  # Leerzeile überspringen statt stoppen
        if is_prose_line(lines[i]):
            prose.append(line)
    return " ".join(reversed(prose))


def split_sections(lines: list) -> list:
    """
    Teilt Markdown in ## Abschnitte auf.
    Gibt Liste von (header, content_lines) zurück.
    """
    sections = []
    current_header = HEADER_SECTION
    current_lines  = []

    for line in lines:
        if line.startswith("## "):
            if current_lines:
                sections.append((current_header, current_lines))
            current_header = line.strip()
            current_lines  = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_header, current_lines))

    return sections


# ── Haupt-Check ───────────────────────────────────────────────────────────────

def check_file(filepath: Path) -> list:
    """
    Analysiert eine einzelne Markdown-Datei.
    Kommentar-Blöcke und Datei-Header werden vor der Analyse ignoriert.
    """
    problems = []

    try:
        raw = filepath.read_text(encoding="utf-8")
    except Exception as e:
        return [("error", f"Datei konnte nicht gelesen werden: {e}")]

    if not raw.strip():
        return [("warning", "Datei ist leer")]

    # Kommentar-Blöcke entfernen
    text  = remove_comment_blocks(raw)
    lines = text.splitlines()

    if not lines:
        return []

    # ── Check 1: Tabellen ohne Prosa-Einleitung ──────────────────────────────
    in_code_block = False
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
        if not in_code_block and line.strip().startswith("|") and "---" not in line:
            prose_before = get_prose_before(lines, i)
            if len(prose_before) < MIN_PROSE_BEFORE:
                problems.append((
                    "error",
                    f"Tabelle ohne Prosa-Einleitung (Zeile {i + 1})"
                ))

    # ── Check 2: Codeblöcke ohne Prosa-Einleitung ────────────────────────────
    for i, line in enumerate(lines):
        if line.strip().startswith("```") and len(line.strip()) > 3:
            prose_before = get_prose_before(lines, i)
            if len(prose_before) < MIN_PROSE_BEFORE:
                problems.append((
                    "error",
                    f"Codeblock ohne Prosa-Einleitung (Zeile {i + 1})"
                ))

    # ── Check 3, 4: Abschnitte prüfen (Datei-Header überspringen) ────────────
    sections = split_sections(lines)
    for header, content in sections:

        # Datei-Header überspringen
        if header == HEADER_SECTION:
            continue

        non_empty = [l for l in content if l.strip()]
        if len(non_empty) < 3:
            continue

        # Check 3: Zu viele Listen
        list_lines = [l for l in non_empty if l.strip().startswith(("-", "*", "+"))]
        ratio = len(list_lines) / len(non_empty)
        if ratio >= LIST_RATIO:
            problems.append((
                "error",
                f"Abschnitt '{header}' besteht zu {int(ratio*100)}% aus Listen – keine Sätze"
            ))

        # Check 4: Zu kurze Abschnitte
        prose_only = " ".join(l.strip() for l in content if is_prose_line(l))
        if 0 < len(prose_only) < MIN_SECTION_CHARS:
            problems.append((
                "warning",
                f"Abschnitt '{header}' hat nur {len(prose_only)} Zeichen Prosa (zu kurz)"
            ))

    # ── Check 5: Zu niedriger Prosa-Anteil gesamt (Datei-Header einberechnet) ─
    non_empty_lines = [l for l in lines if l.strip()]
    if non_empty_lines:
        prose_lines = [l for l in non_empty_lines if is_prose_line(l)]
        prose_ratio = len(prose_lines) / len(non_empty_lines)
        if prose_ratio < MIN_PROSE_RATIO:
            problems.append((
                "warning",
                f"Prosa-Anteil nur {int(prose_ratio*100)}% "
                f"({len(prose_lines)}/{len(non_empty_lines)} Zeilen) – zu wenig Text"
            ))

    return problems


# ── Ausgabe ───────────────────────────────────────────────────────────────────

def run_check():
    docs_path = Path(DOCS_PATH)

    if not docs_path.exists():
        print(f"❌ Docs-Pfad nicht gefunden: {docs_path.resolve()}")
        return

    all_files = sorted(docs_path.rglob("*.md"))

    if not all_files:
        print("⚠️  Keine Markdown-Dateien gefunden.")
        return

    files_ok      = 0
    files_warning = 0
    files_error   = 0
    total_problems = 0

    problem_section = []
    warning_section = []
    ok_section      = []

    for filepath in all_files:
        relative = filepath.relative_to(docs_path)
        problems = check_file(filepath)
        errors   = [p for p in problems if p[0] == "error"]
        warnings = [p for p in problems if p[0] == "warning"]

        if errors:
            files_error    += 1
            total_problems += len(errors) + len(warnings)
            block = f"### {relative}\n"
            for _, msg in errors:
                block += f"- ❌ {msg}\n"
            for _, msg in warnings:
                block += f"- ⚠️ {msg}\n"
            problem_section.append(block + "\n")

        elif warnings:
            files_warning  += 1
            total_problems += len(warnings)
            block = f"### {relative}\n"
            for _, msg in warnings:
                block += f"- ⚠️ {msg}\n"
            warning_section.append(block + "\n")

        else:
            files_ok += 1
            ok_section.append(f"- ✅ {relative}\n")

    # ── Report schreiben ──────────────────────────────────────────────────────
    report = []
    report.append("# SUSI Docs Quality Report\n\n")
    report.append(f"Dateien geprüft: **{len(all_files)}**\n\n")
    report.append("---\n\n")

    report.append("## ❌ Probleme\n\n")
    report.extend(problem_section if problem_section else ["_Keine Probleme gefunden._\n\n"])

    report.append("## ⚠️ Warnungen\n\n")
    report.extend(warning_section if warning_section else ["_Keine Warnungen._\n\n"])

    report.append("## ✅ OK\n\n")
    report.extend(ok_section)

    report_path = Path(REPORT_PATH)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("".join(report), encoding="utf-8")

    # ── Konsole: nur Zusammenfassung ─────────────────────────────────────────
    print(f"\n{'═' * 50}")
    print(f"  📊 SUSI Docs Quality Check")
    print(f"{'═' * 50}")
    print(f"  ✅ OK:        {files_ok} Dateien")
    print(f"  ⚠️  Warnungen: {files_warning} Dateien")
    print(f"  ❌ Probleme:  {files_error} Dateien")
    print(f"  📌 Gesamt:    {total_problems} Probleme")
    print(f"{'═' * 50}")
    print(f"  → Details: {REPORT_PATH}")
    print()


if __name__ == "__main__":
    run_check()