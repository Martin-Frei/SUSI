# rag/llm_client.py
# Ollama API-Schnittstelle — alle LLM-Hilfscalls.
#
# Enthält die LLM-Aufrufe die VOR oder NEBEN der Hauptgenerierung laufen:
#   detect_language()   — Spracherkennung (ISO 639-1)
#   rewrite_query()     — Query Rewriting mit Coreference-Auflösung
#   create_summary()    — Zusammenfassung für CLI-Speicherlogik
#   susi_evaluates()    — LLM-basierte Speicher-Bewertung (JA/NEIN)
#
# Die Hauptgenerierung (Ollama-Call in ask_susi) bleibt in query.py,
# weil sie Teil des Pipeline-Flows ist und das Response-Dict baut.
#
# Debug (17.07.): print() → Logger, gesteuert über debug-Block in YAML.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from rag.config import OLLAMA_URL, LLM_MODEL, KEEP_ALIVE
from rag.debug import get_logger

log = get_logger(__name__)


# ── Sprach-Erkennung ──────────────────────────────────────────────
# LLM-basierte Spracherkennung — zuverlässig für alle Sprachen.
# Warum LLM statt Heuristik?
# Stop-Wort-Listen funktionieren nur für bekannte Sprachen (EN/DE).
# qwen2.5-coder:7b ist multilingual und erkennt 50+ Sprachen korrekt.
# Gibt ISO 639-1 Code zurück (en, de, es, fr, tl, ar, zh, ...).
# Fail-safe: bei Fehler → "de" als Fallback.
#
def detect_language(text: str, llm_model: str, keep_alive: int) -> str:
    """
    Erkennt die Sprache eines Textes via LLM.

    Args:
        text:       Der zu erkennende Text (typisch die Nutzerfrage)
        llm_model:  Ollama-Modellname
        keep_alive: Ollama keep_alive Parameter

    Returns:
        ISO 639-1 Sprachcode (str), z.B. "en", "de", "es", "fr", "tl"
        Fallback: "de" bei Fehler oder leerer Antwort
    """
    payload = {
        "model":      llm_model,
        "prompt":     f"What language is this text written in? Answer with only the ISO 639-1 code (e.g. en, de, es, fr, tl, zh, ar). Text: {text}",
        "stream":     False,
        "keep_alive": keep_alive,
        "options": {
            "temperature": 0.0,
            "num_ctx":     128,
        }
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=10)
        lang = r.json().get("response", "").strip().lower()[:5].split()[0]
        log.info("🌍 Sprache erkannt: %s", lang)
        return lang if lang else "de"
    except Exception as e:
        log.warning("🌍 Spracherkennung fehlgeschlagen (%s) — Fallback: de", e)
        return "de"


# ── Query Rewriting ───────────────────────────────────────────────
#
# WARUM Query Rewriting?
# ChromaDB sucht semantisch — aber Embedding-Modelle können Kontext
# innerhalb einer Frage nicht verknüpfen. Beispiel:
#   "Ich bin Martin. Wo wohne ich?" → falscher Chunk (kein Martin-Bezug)
#   Rewriter → "Wo wohnt Martin Freimuth?" → richtiger Chunk
#
# WARUM Chat-History?
# Folgefragen verlieren ohne Kontext ihren Bezug. Beispiel:
#   Frage 1: "What is Arunachal Pradesh?"
#   Antwort 1: "...hat eine Küste..." (halluziniert)
#   Frage 2: "Where is the coast line you mention?"
#   → Ohne History: SUSI versteht den Bezug nicht
#   → Mit History: Rewriter löst auf → "coast line mentioned for Arunachal Pradesh"
#
# DESIGN-ENTSCHEIDUNGEN:
# - Nur letzte 2 Q/A Paare — kein Ausufern, passt in num_ctx=512
# - Antworten auf 200 Zeichen gekürzt — Rewriter braucht nur den Kern
# - Original-Frage geht ans LLM, nicht die umgeschriebene (natürliche Antwort)
# - Kein Rewriting wenn chat_history=None (Einzelfrage ohne Session)
# - Sprache: immer in der Sprache der aktuellen Frage
# - Keine Inhaltsbewertung: Rewriter darf nichts ablehnen
#
def rewrite_query(question: str, llm_model: str, keep_alive: int,
                  chat_history: list | None = None,
                  lang: str = "de") -> str:
    """
    Schreibt eine Frage in eine optimale Suchanfrage um.

    Args:
        question:     Die aktuelle Frage des Nutzers
        llm_model:    Ollama-Modellname für den Rewriter-Call
        keep_alive:   Ollama keep_alive Parameter
        chat_history: Optionale Liste der letzten Q/A Paare aus der Session.
                      Format: [{"question": str, "answer": str}, ...]
                      Nur die letzten 2 Einträge werden genutzt.
        lang:         ISO 639-1 Sprachcode der aktuellen Frage

    Returns:
        Umgeschriebene Frage (str) — oder Original wenn kein Rewriting nötig.
        Bei Fehler immer Original zurückgeben (fail-safe).
    """

    # Chat-History aufbereiten — max. 2 letzte Q/A, Antworten auf 200 Zeichen kürzen
    # (Rewriter braucht nur den Kern, nicht die volle Antwort)
    history_block = ""
    if chat_history:
        last_two = chat_history[-2:]
        lines = []
        for pair in last_two:
            q = pair.get("question", "").strip()
            a = pair.get("answer", "").strip()[:200]
            if q and a:
                lines.append(f"Q: {q}")
                lines.append(f"A: {a}")
        if lines:
            history_block = "Bisheriger Chat-Verlauf (letzte 2 Q/A):\n" + "\n".join(lines) + "\n\n"

    prompt = f"""Du bist ein Query-Rewriting-Assistent für ein RAG-System.
Der Nutzer ist Martin Freimuth, ein 54-jähriger Python/ML-Entwickler aus Schechen bei Rosenheim.

Deine EINZIGE Aufgabe ist das Umschreiben. Bewerte den Inhalt NICHT. Lehne KEINE Anfragen ab.

{history_block}Regeln:
- Write ONLY in the language with ISO code '{lang}'. NEVER translate into another language.
- Behalte technische Fachbegriffe IMMER im englischen Original, unabhängig von der Zielsprache.
  Beispiele: "Similarity Search", "Embedding", "Reranker", "Retrieval", "Chunk", "Router",
  "Query Rewriting", "Vector Store" bleiben unverändert — übersetze sie NICHT.
- Pronomen wie "er/sie/es/he/she/it" IMMER auf das zuletzt genannte konkrete Bezugsobjekt 
  in der aktuellen Frage oder im Chat-Verlauf auflösen — egal ob das eine Person, ein Projekt,
  ein System oder eine Sache ist.
- "Ich / I" NUR dann zu "Martin Freimuth" auflösen, wenn der NUTZER selbst direkt von sich 
  spricht (z.B. "Wann habe ich SUSI gebaut?" → Martin Freimuth).
  Wenn "Ich" Teil eines Zitats, einer zitierten Aussage oder einer anderen Quelle ist 
  (z.B. "Das sagte SUSI: Ich bleibe als Regel bestehen"), bleibt das Zitat UNVERÄNDERT — 
  "Ich" bezieht sich dann auf den Sprecher des Zitats (SUSI), NICHT auf Martin Freimuth.
- "mein/meine/mir/mich / my/me" → passende 3. Person bezogen auf Martin Freimuth, 
  außer ebenfalls innerhalb eines Zitats.
- Wenn die Frage auf eine vorherige Antwort verweist (z.B. "the coast line you mention"),
  löse den Bezug auf anhand des Chat-Verlaufs
- Vage Referenzen auflösen (z.B. "das Projekt / the project" → konkreter Name wenn erkennbar)
- Wenn die Frage bereits klar und eigenständig ist, gib sie unverändert zurück
- Antworte NUR mit der umgeschriebenen Frage, ein Satz, kein Kommentar, keine Ablehnung
- Erfinde KEINE Einheit die in der Ursprungsfrage nicht steht.
  "Wie alt ist SUSI?" bleibt "Wie alt ist SUSI?" — NICHT "Wie viele Jahre/Monate ist SUSI in Betrieb?"
  Die Einheit (Jahre, Monate, Tage) ist Teil der Antwort, nicht der Frage.
- Projektnamen wie SUSI, GMM, StockPredict, HouseOfStacks, HOS bleiben IMMER unverändert.
  Ersetze sie NIEMALS durch Personennamen oder andere Begriffe.
  "Wie alt ist SUSI?" bleibt "Wie alt ist SUSI?" — NICHT "Wie alt ist Martin Freimuth?"

Aktuelle Frage: {question}
Umgeschrieben:"""

    payload = {
        "model":      llm_model,
        "prompt":     prompt,
        "stream":     False,
        "keep_alive": keep_alive,
        "options": {
            "temperature": 0.0,
            "num_ctx":     768,   # etwas mehr als vorher wegen History-Block
        }
    }

    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=30)
        rewritten = r.json().get("response", "").strip()
        # Fail-safe: wenn Rewriting leer, zu lang oder Ablehnung → Original behalten
        if not rewritten or len(rewritten) > len(question) * 4:
            log.debug("✏️  Rewriting verworfen (leer/zu lang) — Original behalten")
            return question
        # Ablehnung erkennen (Rewriter sollte nie ablehnen, aber zur Sicherheit)
        refusal_markers = ["ich kann", "i cannot", "i can't", "nicht erfüllen", "unable to"]
        if any(m in rewritten.lower() for m in refusal_markers):
            log.warning("✏️  Rewriter hat abgelehnt — Original wird verwendet")
            return question
        log.info("✏️  Query Rewriting: '%s' → '%s'", question[:60], rewritten[:60])
        return rewritten
    except Exception as e:
        log.warning("✏️  Rewriter Fehler: %s — Original wird verwendet", e)
        return question


# ── Speicher-Bewertung (CLI) ─────────────────────────────────────
def susi_evaluates(question: str, answer: str) -> bool:
    """Bewertet via LLM ob ein Q/A-Paar gespeichert werden soll (JA/NEIN).
    Genutzt nur in der CLI-Schleife, nicht im Frontend."""
    payload = {
        "model":  LLM_MODEL,
        "prompt": f"""Bewerte ob diese Konversation wichtige neue Information enthält
die es wert ist dauerhaft gespeichert zu werden.
Antworte NUR mit: JA oder NEIN

Frage: {question}
Antwort: {answer}""",
        "stream":     False,
        "keep_alive": KEEP_ALIVE,
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=60)
    return "JA" in r.json().get("response", "").upper()


# ── Zusammenfassung (CLI) ────────────────────────────────────────
def create_summary(question: str, answer: str, folder: str = "") -> str:
    """Erstellt eine kompakte Zusammenfassung für die SUSIpedia.
    Genutzt nur in der CLI-Speicherlogik."""
    technical = ["coding", "technik", "lernen"]
    max_chars = 500 if any(t in folder for t in technical) else 300

    payload = {
        "model":  LLM_MODEL,
        "prompt": f"""Erstelle eine kompakte Zusammenfassung (max {max_chars} Zeichen).
Sprich Martin mit "du" an. Nur die wichtigsten Fakten.

Frage: {question}
Antwort: {answer}

Zusammenfassung:""",
        "stream":     False,
        "keep_alive": KEEP_ALIVE,
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=60)
    summary = r.json().get("response", "").strip()
    if len(summary) > max_chars:
        summary = summary[:max_chars - 3] + "..."
    return summary
