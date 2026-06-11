"""
fix_comment_blocks.py
=====================
Sucht in allen Markdown-Dateien der SUSIpedia nach definierten Abschnitt-Mustern
und wrappt diese automatisch mit Kommentar-Block Tags die ingest.py dann
beim Indexieren überspringt.

HINTERGRUND:
    Abschnitte wie '## Offene Punkte' oder '## TODO' enthalten meist nur Listen
    die für RAG-Retrieval ungeeignet sind. Statt diese Abschnitte zu löschen
    werden sie mit ##** ... **## markiert damit ingest.py sie ignoriert.
    Der Inhalt bleibt in der Datei erhalten – nur ChromaDB bekommt ihn nicht.

WIE ES FUNKTIONIERT:
    Das Script liest jede .md Datei und sucht nach Abschnitt-Headern die in
    COMMENT_PATTERNS definiert sind. Alles von diesem Header bis zum nächsten
    ## Header (oder Dateiende) wird mit COMMENT_START und COMMENT_END gewrappt.

    Vorher:
        ## Offene Punkte
        - Task A
        - Task B

        ## Nächster Abschnitt

    Nachher:
        ##** Offene Punkte
        - Task A
        - Task B
        **##

        ## Nächster Abschnitt

    WICHTIG: COMMENT_END (**##) erscheint NUR einmal am Ende des Blocks.
    Der Header bekommt nur COMMENT_START (##**) ohne COMMENT_END.

DRY_RUN MODUS:
    Wenn DRY_RUN = True wird nur angezeigt welche Dateien und Abschnitte
    geändert würden – es wird nichts geschrieben. Zum Testen immer zuerst
    mit DRY_RUN = True ausführen, dann auf False setzen.

STELLSCHRAUBEN:
    DOCS_PATH         → Pfad zur SUSIpedia (relativ zum Projektroot)
    COMMENT_PATTERNS  → Liste der Abschnitt-Header die gewrappt werden
                        Unterstützt Präfix-Matching: "## Offene Punkte"
                        matcht auch "## Offene Punkte 28.02.2026"
    COMMENT_START     → Öffnungs-Tag (muss mit ingest.py übereinstimmen)
    COMMENT_END       → Schließ-Tag (muss mit ingest.py übereinstimmen)
    DRY_RUN           → True = nur anzeigen, False = wirklich schreiben
    BACKUP            → True = .bak Datei vor dem Schreiben erstellen

AUSFÜHREN:
    # Erst testen (DRY_RUN = True):
    python tools/fix_comment_blocks.py

    # Dann wirklich schreiben (DRY_RUN = False):
    python tools/fix_comment_blocks.py

DANACH:
    python rag/ingest.py
    python tools/check_docs_quality.py
"""

from pathlib import Path
import shutil

# ── Stellschrauben ────────────────────────────────────────────────────────────

DOCS_PATH = "docs"

# Abschnitt-Header die als Kommentar-Block gewrappt werden.
# Präfix-Matching: "## Offene Punkte" matcht auch "## Offene Punkte 28.02.2026"
COMMENT_PATTERNS = [
    "## Offene Punkte",
    "## Noch offen",
    "## Review Backlog",
    "## TODO",
    "## Notizen",
    "## Hinweise",
    "## Anmerkungen",
]

# Tags müssen mit ingest.py übereinstimmen
COMMENT_START = "##**"
COMMENT_END   = "**##"

# True = nur anzeigen was geändert würde, nichts schreiben
DRY_RUN = False

# True = .bak Datei vor dem Schreiben erstellen
BACKUP = False

# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def matches_pattern(line: str) -> bool:
    """
    Prüft ob eine Zeile einem der definierten Kommentar-Muster entspricht.
    Präfix-Matching: "## Offene Punkte" matcht auch "## Offene Punkte V1.1"
    Bereits gewrappte Blöcke (##**) werden ignoriert.
    """
    stripped = line.strip()
    if stripped.startswith(COMMENT_START):
        return False  # bereits gewrappt
    return any(stripped.startswith(pattern) for pattern in COMMENT_PATTERNS)


def wrap_file(filepath: Path, dry_run: bool = True) -> list:
    """
    Verarbeitet eine einzelne Markdown-Datei.
    Gibt Liste der gefundenen Änderungen zurück: [(zeilennummer, header)]
    Schreibt die Datei wenn dry_run=False.

    Format:
        ##** Offene Punkte        ← nur COMMENT_START, kein COMMENT_END
        - Task A
        **##                      ← COMMENT_END nur einmal am Blockende
    """
    text  = filepath.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    changes   = []
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if matches_pattern(line):
            # Header-Text extrahieren (## entfernen)
            header_text = line.strip()[3:].strip()
            changes.append((i + 1, line.strip()))

            # Öffnungs-Tag schreiben — NUR ##** ohne **## am Ende
            new_lines.append(f"{COMMENT_START} {header_text}\n")
            i += 1

            # Alles bis zum nächsten ## Header oder Dateiende sammeln
            block_lines = []
            while i < len(lines):
                next_line = lines[i]
                if next_line.startswith("## ") or next_line.startswith("# "):
                    break
                block_lines.append(next_line)
                i += 1

            # Block-Inhalt schreiben
            new_lines.extend(block_lines)

            # Schließ-Tag — einmal am Ende des Blocks
            new_lines.append(f"{COMMENT_END}\n")

        else:
            new_lines.append(line)
            i += 1

    if changes and not dry_run:
        if BACKUP:
            shutil.copy2(filepath, str(filepath) + ".bak")
        filepath.write_text("".join(new_lines), encoding="utf-8")

    return changes


# ── Haupt-Funktion ────────────────────────────────────────────────────────────

def run():
    docs_path = Path(DOCS_PATH)

    if not docs_path.exists():
        print(f"❌ Docs-Pfad nicht gefunden: {docs_path.resolve()}")
        return

    all_files = sorted(docs_path.rglob("*.md"))

    if not all_files:
        print("⚠️  Keine Markdown-Dateien gefunden.")
        return

    mode = "DRY RUN – nichts wird geschrieben" if DRY_RUN else "SCHREIB-MODUS – Dateien werden geändert"

    print(f"\n{'═' * 55}")
    print(f"  🔧 SUSI fix_comment_blocks")
    print(f"  Modus: {mode}")
    print(f"{'═' * 55}\n")

    total_files   = 0
    total_changes = 0

    for filepath in all_files:
        relative = filepath.relative_to(docs_path)

        try:
            changes = wrap_file(filepath, dry_run=DRY_RUN)
        except Exception as e:
            print(f"❌ {relative}: Fehler – {e}")
            continue

        if changes:
            total_files   += 1
            total_changes += len(changes)
            print(f"{'📋' if DRY_RUN else '✅'} {relative}")
            for line_nr, header in changes:
                print(f"   → Zeile {line_nr}: {header}")

    print(f"\n{'═' * 55}")
    if DRY_RUN:
        print(f"  📋 DRY RUN abgeschlossen")
        print(f"  {total_changes} Abschnitte in {total_files} Dateien würden gewrappt")
        print(f"\n  → DRY_RUN = False setzen um wirklich zu schreiben")
    else:
        print(f"  ✅ Fertig!")
        print(f"  {total_changes} Abschnitte in {total_files} Dateien gewrappt")
        if BACKUP:
            print(f"  💾 Backup-Dateien erstellt (.bak)")
        print(f"\n  → Jetzt: python rag/ingest.py")
        print(f"  → Dann:  python tools/check_docs_quality.py")
    print()


if __name__ == "__main__":
    run()