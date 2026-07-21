# rag/utils.py
# Hilfsfunktionen & Dateisystem — CLI-Speicherlogik.
#
# Enthält alles rund um das Speichern in die SUSIpedia (CLI-Modus):
#   get_time()           — Zeitstempel für Prompts ("DD.MM.YYYY HH:MM Uhr")
#   get_date()           — Zeitstempel für Datei-Einträge ("DD.MM.YYYY HH:MM")
#   worth_saving()       — Filtert triviale Fragen raus
#   get_suggestions()    — Ordner-Vorschläge aus Keyword-Matching
#   save_to_susipedia()  — Schreibt Zusammenfassung in SUSIpedia-Datei
#   show_save_prompt()   — Interaktiver CLI-Dialog zum Speichern
#
# Debug (17.07.): print() → Logger für die Speicher-Aktionen.
# Die interaktiven CLI-Dialoge (show_save_prompt) bleiben print/input —
# das ist User-Interaktion, kein Logging.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subprocess
from datetime import datetime
import pytz

from rag.config import DOCS_PATH
from rag.keywords import TOPIC_KEYWORDS, UNWICHTIG
from rag.llm_client import create_summary
from rag.debug import get_logger

log = get_logger(__name__)


def get_time() -> str:
    """Zeitstempel für System-Prompts: 'DD.MM.YYYY HH:MM Uhr'"""
    tz = pytz.timezone("Europe/Berlin")
    return datetime.now(tz).strftime("%d.%m.%Y %H:%M Uhr")


def get_date() -> str:
    """Zeitstempel für Datei-Einträge: 'DD.MM.YYYY HH:MM'"""
    tz = pytz.timezone("Europe/Berlin")
    return datetime.now(tz).strftime("%d.%m.%Y %H:%M")


def worth_saving(question: str) -> bool:
    """True wenn die Frage potenziell speicherwürdig ist.
    Filtert triviale Phrasen (Hallo, Danke, etc.) raus."""
    q_lower = question.lower()
    return not any(phrase in q_lower for phrase in UNWICHTIG)


def get_suggestions(question: str, answer: str) -> list[str]:
    """Schlägt passende SUSIpedia-Ordner vor basierend auf Keyword-Matching.
    Gibt die Top-2 Ordner zurück, Fallback: ['persoenlich/']."""
    combined = (question + " " + answer).lower()
    scores = {
        folder: sum(1 for kw in keywords if kw in combined)
        for folder, keywords in TOPIC_KEYWORDS.items()
    }
    top2 = sorted(
        (f for f in scores if scores[f] > 0),
        key=lambda f: scores[f],
        reverse=True,
    )[:2]
    result = top2 if top2 else ["persoenlich/"]
    log.debug("💾 Ordner-Vorschläge: %s", result)
    return result


def save_to_susipedia(question: str, answer: str, folder: str) -> None:
    """Speichert eine LLM-Zusammenfassung als neuen Abschnitt in einer
    SUSIpedia-Datei und löst danach eine Neuindexierung aus."""
    summary = create_summary(question, answer, folder)
    date = get_date()

    if not folder.endswith(".md"):
        filename = folder.rstrip("/").split("/")[-1] + ".md"
        filepath = os.path.join(DOCS_PATH, folder.rstrip("/"), filename)
    else:
        filepath = os.path.join(DOCS_PATH, folder)

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    new_section = f"\n## Gespräch {date}\n{summary}\n"

    if os.path.exists(filepath):
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(new_section)
        log.info("✅ Erweitert: %s", filepath)
    else:
        title = folder.rstrip("/").split("/")[-1].capitalize()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n{new_section}")
        log.info("✅ Neu erstellt: %s", filepath)

    log.info("🔄 SUSIpedia wird aktualisiert...")
    subprocess.run(["python", "rag/ingest.py"], capture_output=True)
    log.info("🎉 SUSIpedia aktualisiert!")


def show_save_prompt(question: str, answer: str) -> None:
    """Interaktiver CLI-Dialog: fragt ob und wohin gespeichert werden soll.
    Bewusst print/input statt Logger — das ist User-Interaktion."""
    suggestions = get_suggestions(question, answer)
    print("\n💾 Speichern in SUSIpedia?")
    print("  1. Nicht speichern")
    for i, s in enumerate(suggestions, 2):
        print(f"  {i}. {s}")
    print(f"  {len(suggestions) + 2}. Anderen Ordner eingeben")

    choice = input("\nWahl: ").strip()
    if choice == "1":
        return
    elif choice == str(len(suggestions) + 2):
        custom = input("Ordner eingeben (z.B. hobbys/tanzen): ").strip()
        save_to_susipedia(question, answer, custom)
    else:
        try:
            idx = int(choice) - 2
            if 0 <= idx < len(suggestions):
                save_to_susipedia(question, answer, suggestions[idx])
        except ValueError:
            print("  ⚠️ Ungültige Eingabe – nicht gespeichert")
