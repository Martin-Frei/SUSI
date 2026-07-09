# rag/query.py
# Aktivieren: susi_env\Scripts\activate
# Starten:    python rag/query.py

import os
import time
import subprocess
import requests
import yaml
from datetime import datetime
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from sentence_transformers import CrossEncoder
import pytz

from rag.router import get_profile, apply_profile
from rag import agent_datum

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
        print(f"  🌍 Sprache erkannt: {lang}")
        return lang if lang else "de"
    except Exception:
        return "de"


# ── Config laden ──────────────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "susi_config.yaml")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

cfg = load_config()

CHROMA_PATH     = cfg["retrieval"]["chroma_path"]
DOCS_PATH       = cfg["paths"]["docs"]
EMBEDDING_MODEL = cfg["retrieval"]["embedding_model"]
LLM_MODEL       = cfg["generation"]["llm_model"]
KEEP_ALIVE      = cfg["generation"]["keep_alive"]
OLLAMA_URL      = "http://localhost:11434/api/generate"

# ── Reranker (einmalig laden) ──────────────────────────────────────
_reranker_cfg   = cfg.get("reranker", {})
RERANKER_ACTIVE = _reranker_cfg.get("active", False)
RERANKER_MODEL  = _reranker_cfg.get("model", "BAAI/bge-reranker-v2-m3")

_reranker = None
def get_reranker():
    global _reranker
    if _reranker is None and RERANKER_ACTIVE:
        print(f"  🔁 Lade Reranker: {RERANKER_MODEL}")
        _reranker = CrossEncoder(RERANKER_MODEL)
    return _reranker

# ── Ordner-Struktur für Vorschläge ────────────────────────────────
TOPIC_KEYWORDS = {
    "hobbys/tanzen":        ["tanz", "walzer", "salsa", "bachata", "kizomba", "boogie", "rumba", "jive", "samba"],
    "hobbys/musik":         ["musik", "song", "metal", "klassik", "playlist"],
    "coding/stockpredict":  ["stockpredict", "lstm", "xgboost", "trading", "pipeline", "backtest"],
    "coding/houseofstocks": ["houseofstocks", "django", "apscheduler", "allauth"],
    "coding/gmm":           ["gmm", "global market mood", "marketmood", "vader", "finbert",
                             "sentiment", "rss", "klassifikation", "deepseek", "pgvector",
                             "feeds", "artikel", "topic", "geopolitics"],
    "coding/susi":          ["susi", "rag", "chromadb", "langchain", "ollama"],
    "coding/portfolio":     ["portfolio", "secret lab", "martin-freimuth"],
    "job/bewerbungen":      ["bewerbung", "firma", "stelle", "job", "arbeit", "gehalt"],
    "finanzen/trading":     ["kapital", "geld", "erbschaft", "aktien", "rendite"],
    "wohnen/suche":         ["wohnung", "miete", "rosenheim", "zimmer", "besichtigung"],
    "familie/sohn":         ["sohn", "kind", "borderline"],
    "persoenlich/":         ["gefühl", "gedanke", "reflexion", "trennung", "beziehung"],
    "technik/":             ["raspberry", "arduino", "whisper", "home assistant"],
}

UNWICHTIG = ["wie spät", "datum", "hallo", "guten morgen", "guten abend",
             "danke", "tschüss", "ok", "super", "gut", "was ist die"]


# ── Hilfsfunktionen ───────────────────────────────────────────────
def get_time():
    tz = pytz.timezone("Europe/Berlin")
    return datetime.now(tz).strftime("%d.%m.%Y %H:%M Uhr")

def get_date():
    tz = pytz.timezone("Europe/Berlin")
    return datetime.now(tz).strftime("%d.%m.%Y %H:%M")


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
            return question
        # Ablehnung erkennen (Rewriter sollte nie ablehnen, aber zur Sicherheit)
        refusal_markers = ["ich kann", "i cannot", "i can't", "nicht erfüllen", "unable to"]
        if any(m in rewritten.lower() for m in refusal_markers):
            print(f"  ⚠️  Rewriter hat abgelehnt — Original wird verwendet")
            return question
        print(f"  ✏️  Query Rewriting: '{question[:60]}' → '{rewritten[:60]}'")
        return rewritten
    except Exception as e:
        print(f"  ⚠️  Rewriter Fehler: {e} — Original wird verwendet")
        return question


# ── Kern-Funktion ─────────────────────────────────────────────────
def ask_susi(question, chat_history: list | None = None, mode: str = "auto",
             overrides: dict | None = None):
    """
    Stellt eine Frage an SUSI und gibt ein Dict zurück.

    Args:
        question:     Die aktuelle Frage des Nutzers
        chat_history: Optionale Session-History für den Query Rewriter.
                      Format: [{"question": str, "answer": str}, ...]
                      Wird von views.py befüllt — max. letzte 2 Q/A Paare.
                      None = kein Chat-Kontext (z.B. erste Frage der Session)
        mode:         Frontend-Modus, gesetzt vom Chat-Toggle.
                      "auto"    = Standard-Pipeline, Router aktiv
                      "manuell" = overrides gewinnen, Router aus
                      "coding"  = Ingest-Vorbereitung (kein Agent)
                      agent_datum ist bei auto UND manuell aktiv —
                      eine Kalenderfrage ist deterministisch beantwortbar
                      egal welches LLM eingestellt ist.
        overrides:    Manuell-Einstellungen aus dem Frontend (views.py,
                      chat.manuell_settings). Keys: llm_model, top_k,
                      temperature, num_ctx, system_prompt (Name!),
                      algorithm, thinking. Wenn gesetzt: Router wird
                      übersprungen, diese Werte gewinnen.
                      system_prompt wird über cfg["system_prompts"]
                      vom Namen auf den Prompt-Text aufgelöst.

    Returns:
        {
            "answer":                str,
            "tok_per_sec":           float,
            "antwortzeit_sek":       float,
            "tokens_generiert":      int,
            "quelldateien":          list[str],
            "llm_model":             str,
            "embedding_model":       str,
            "reranker_used":         bool,
            "chunks_gefunden":       int,
            "chunks_nach_reranking": int,
            "router_profil":         str,
            "thinking":              bool,
            "rewritten_query":       str,
        }
    """
    now = get_time()

    # Mode normalisieren — das Frontend sendet "AUTO"/"MANUELL"/"CODING"
    # (Großbuchstaben aus set_mode_view), intern arbeiten wir lowercase.
    mode = (mode or "auto").lower()

    # Config frisch laden (damit Frontend-Änderungen sofort wirken)
    cfg = load_config()

    # Fallback-Parameter aus Config
    top_k           = cfg["retrieval"]["top_k"]
    algorithm       = cfg["retrieval"]["algorithm"]
    llm_model       = cfg["generation"]["llm_model"]
    temperature     = cfg["generation"]["temperature"]
    num_ctx         = cfg["generation"]["num_ctx"]
    keep_alive      = cfg["generation"]["keep_alive"]
    prompt_name     = cfg["generation"]["system_prompt"]
    system_prompt   = cfg["system_prompts"][prompt_name]
    thinking        = False

    reranker_active = cfg.get("reranker", {}).get("active", False)
    reranker_top_n  = cfg.get("reranker", {}).get("top_n", 3)
    router_active   = cfg.get("router", {}).get("active", False)
    query_rewrite   = cfg.get("query_rewriting", {}).get("active", True)
    router_profil   = "fallback"

    # ── MANUELL-Modus: Overrides anwenden (07.07.2026) ────────────
    # Wenn views.py Overrides mitgibt (chat.manuell_settings), gewinnen
    # diese über die Config-Fallbacks und der Router wird deaktiviert.
    # Früh angewendet damit auch detect_language und rewrite_query das
    # gewählte Modell nutzen — der User hat es bewusst eingestellt.
    # system_prompt kommt als NAME an und wird hier auf den Text aufgelöst.
    if overrides:
        llm_model   = overrides.get("llm_model", llm_model)
        top_k       = int(overrides.get("top_k", top_k))
        temperature = float(overrides.get("temperature", temperature))
        num_ctx     = int(overrides.get("num_ctx", num_ctx))
        algorithm   = overrides.get("algorithm", algorithm)
        thinking    = bool(overrides.get("thinking", False))
        override_prompt_name = overrides.get("system_prompt")
        if override_prompt_name and override_prompt_name in cfg["system_prompts"]:
            system_prompt = cfg["system_prompts"][override_prompt_name]
        router_active = False
        router_profil = "manuell"
        print(f"  🎛️  MANUELL: {llm_model} | k={top_k} | t={temperature} "
              f"| ctx={num_ctx} | thinking={thinking}")

    # 0. Sprache erkennen — vor Agent, Rewriter und Retrieval.
    # Sprache wird VOR dem Rewriter erkannt damit der Rewriter nicht übersetzt.
    # Beispiel: "What is X?" → detect_language() → "en" → Rewriter schreibt auf Englisch um
    lang = detect_language(question, llm_model, keep_alive)

    # 0a. agent_datum — SUSIs erstes Werkzeug im Sinne von Tool Use.
    # Reine Kalenderfragen (Wochentag, Tage/Wochen zwischen zwei Daten,
    # N Tage/Wochen ab heute) werden deterministisch per Python datetime
    # beantwortet — kein LLM, kein Retrieval, keine Halluzination.
    # Aktiv bei auto UND manuell (07.07.): eine Kalenderfrage ist
    # deterministisch beantwortbar egal welches LLM eingestellt ist.
    # Coding = Ingest-Vorbereitung, dort kein Agent.
    # Details zur Klassifikation siehe rag/agent_datum.py.
    if mode in ("auto", "manuell") and lang == "de" and agent_datum.ist_kalenderfrage(question):
        agent_start = time.time()
        agent_antwort = agent_datum.beantworte_kalenderfrage(question)
        agent_wall = round(time.time() - agent_start, 3)
        print(f"  🧮 agent_datum aktiv — deterministische Antwort ({agent_wall}s)")
        return {
            "answer":                agent_antwort,
            "tok_per_sec":           0.0,
            "antwortzeit_sek":       agent_wall,
            "tokens_generiert":      0,
            "quelldateien":          ["🧮 agent_datum (deterministisch)"],
            "llm_model":             "agent_datum",
            "embedding_model":       EMBEDDING_MODEL,
            "reranker_used":         False,
            "chunks_gefunden":       0,
            "chunks_nach_reranking": 0,
            "router_profil":         "agent_datum",
            "thinking":              False,
            "rewritten_query":       question,
        }

    rewritten_query = question
    if query_rewrite:
        rewritten_query = rewrite_query(question, llm_model, keep_alive, chat_history, lang)

    # 1. Retrieval (mit umgeschriebener Frage)
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

    if algorithm == "mmr":
        docs = db.max_marginal_relevance_search(rewritten_query, k=top_k)
    else:
        docs = db.similarity_search(rewritten_query, k=top_k)

    chunks_gefunden = len(docs)

    # 2. Reranking
    reranker_used = False
    ranked_docs = []

    if reranker_active:
        reranker = get_reranker()
        if reranker:
            pairs = [(rewritten_query, doc.page_content) for doc in docs]
            scores = reranker.predict(pairs)
            ranked_docs = sorted(
                zip([float(s) for s in scores], docs),
                key=lambda x: x[0],
                reverse=True
            )
            docs = [doc for _, doc in ranked_docs[:reranker_top_n]]
            reranker_used = True

    # 3. Router — Profil anhand der Top-Chunks bestimmen
    if router_active and ranked_docs:
        folder_profile_map = cfg.get("router", {}).get("folder_profile_map", {})
        profiles           = cfg.get("profiles", {})
        system_prompts     = cfg.get("system_prompts", {})

        fallback_profile = cfg.get("router", {}).get("fallback_profile", "persoenlich")
        profil_name, profil_config = get_profile(ranked_docs[:reranker_top_n], folder_profile_map, profiles, fallback_profile)
        params = apply_profile(profil_config, system_prompts)

        llm_model     = params["llm_model"]
        temperature   = params["temperature"]
        system_prompt = params["system_prompt"]
        thinking      = params["thinking"]
        router_profil = profil_name

        print(f"  🤖 LLM: {llm_model} | thinking: {thinking} | t={temperature}")

    # 4. Kontext zusammenbauen
    context = "\n\n".join([doc.page_content for doc in docs])
    quelldateien = list({doc.metadata.get("source", "?") for doc in docs})

    # 5. Prompt bauen (Original-Frage ans LLM, nicht die umgeschriebene)
    # Sprach-Anweisung explizit im Prompt — verhindert dass qwen auf Deutsch antwortet
    # auch wenn der Kontext oder die SUSIpedia auf Deutsch ist
    # Generische Sprach-Anweisung — funktioniert für alle ISO-Codes
    lang_instruction = f"Answer in the language with ISO code '{lang}'."
    print(f"  🗣️  Sprach-Anweisung: {lang_instruction}")

    prompt = f"""{system_prompt}

Heute ist: {now}

Kontext:
{context}

Frage: {question}

WICHTIG: {lang_instruction}
Antwort:"""

    # 6. Ollama-Payload
    options = {
        "temperature": temperature,
        "num_ctx":     num_ctx,
    }
    if thinking:
        options["thinking"] = True

    payload = {
        "model":      llm_model,
        "prompt":     prompt,
        "stream":     False,
        "keep_alive": keep_alive,
        "options":    options,
    }

    # 7. LLM aufrufen
    start = time.time()
    response = requests.post(OLLAMA_URL, json=payload, timeout=120)
    response.raise_for_status()
    wall_time = round(time.time() - start, 2)

    data = response.json()

    eval_count    = data.get("eval_count", 0)
    eval_duration = data.get("eval_duration", 1)
    tok_per_sec   = round(eval_count / eval_duration * 1e9, 1) if eval_duration > 0 else 0.0

    return {
        "answer":                data.get("response", "").strip(),
        "tok_per_sec":           tok_per_sec,
        "antwortzeit_sek":       wall_time,
        "tokens_generiert":      eval_count,
        "quelldateien":          quelldateien,
        "llm_model":             llm_model,
        "embedding_model":       EMBEDDING_MODEL,
        "reranker_used":         reranker_used,
        "chunks_gefunden":       chunks_gefunden,
        "chunks_nach_reranking": len(docs),
        "router_profil":         router_profil,
        "thinking":              thinking,
        "rewritten_query":       rewritten_query,
    }



# ── Eval-Pipeline ─────────────────────────────────────────────────
def ask_susi_eval(question: str, chat_history: list | None = None) -> dict:
    """
    Komplette SUSI Live-Pipeline fuer die Evaluation (Lauf F).
    NICHT fuer das Frontend -- nur fuer grid_run.py mit --live Flag.

    Identisch zu ask_susi() aber mit zusaetzlichen Eval-Feldern:
        kontext_vor_reranking   str   alle top_k Chunks getrennt durch ---
        kontext_nach_reranking  str   nur top_n Chunks nach Reranker
        chunk_scores            list  [(score, quelle, text[:100])] alle top_k

    Diagnose-Schema:
        Chunk nicht in kontext_vor_reranking  -> Retrieval-Problem (bge-m3)
        Chunk in vor aber nicht in nach       -> Reranker-Problem
        Chunk in nach aber falsche Antwort    -> LLM-Problem
    """
    now = get_time()
    cfg = load_config()

    top_k           = cfg["retrieval"]["top_k"]
    algorithm       = cfg["retrieval"]["algorithm"]
    llm_model       = cfg["generation"]["llm_model"]
    temperature     = cfg["generation"]["temperature"]
    num_ctx         = cfg["generation"]["num_ctx"]
    keep_alive      = cfg["generation"]["keep_alive"]
    prompt_name     = cfg["generation"]["system_prompt"]
    system_prompt   = cfg["system_prompts"][prompt_name]
    thinking        = False

    reranker_active = cfg.get("reranker", {}).get("active", False)
    reranker_top_n  = cfg.get("reranker", {}).get("top_n", 3)
    router_active   = cfg.get("router", {}).get("active", False)
    query_rewrite   = cfg.get("query_rewriting", {}).get("active", True)
    router_profil   = "fallback"

    # 0. Sprache + Rewriting (einmal!)
    lang = detect_language(question, llm_model, keep_alive)

    # 0a. agent_datum — auch in der Eval-Pipeline aktiv, damit grid_run
    # den Produktions-Zustand widerspiegelt. Bei reinen Kalenderfragen
    # muss die Bewertung genau das prüfen was das Frontend auch tut:
    # deterministische Antwort ohne LLM.
    if lang == "de" and agent_datum.ist_kalenderfrage(question):
        agent_start = time.time()
        agent_antwort = agent_datum.beantworte_kalenderfrage(question)
        agent_wall = round(time.time() - agent_start, 3)
        print(f"  🧮 agent_datum aktiv — deterministische Antwort ({agent_wall}s)")
        return {
            "answer":                 agent_antwort,
            "tok_per_sec":            0.0,
            "antwortzeit_sek":        agent_wall,
            "tokens_generiert":       0,
            "quelldateien":           ["🧮 agent_datum (deterministisch)"],
            "llm_model":              "agent_datum",
            "embedding_model":        EMBEDDING_MODEL,
            "reranker_used":          False,
            "chunks_gefunden":        0,
            "chunks_nach_reranking":  0,
            "router_profil":          "agent_datum",
            "thinking":               False,
            "rewritten_query":        question,
            "kontext_vor_reranking":  "",
            "kontext_nach_reranking": "",
            "chunk_scores":           [],
        }

    rewritten_query = question
    if query_rewrite:
        rewritten_query = rewrite_query(question, llm_model, keep_alive, chat_history, lang)

    # 1. Retrieval
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

    if algorithm == "mmr":
        docs = db.max_marginal_relevance_search(rewritten_query, k=top_k)
    else:
        docs = db.similarity_search(rewritten_query, k=top_k)

    chunks_gefunden = len(docs)

    # Kontext VOR Reranking speichern
    kontext_vor = "\n---\n".join(
        f"[{d.metadata.get('source', '?')}]\n{d.page_content}" for d in docs
    )

    # 2. Reranking
    reranker_used = False
    ranked_docs = []
    chunk_scores = []

    if reranker_active:
        reranker = get_reranker()
        if reranker:
            pairs = [(rewritten_query, doc.page_content) for doc in docs]
            scores = reranker.predict(pairs)
            ranked_docs = sorted(
                zip([float(s) for s in scores], docs),
                key=lambda x: x[0],
                reverse=True
            )
            chunk_scores = [
                (round(s, 4), d.metadata.get("source", "?"), d.page_content[:100])
                for s, d in ranked_docs
            ]
            docs = [doc for _, doc in ranked_docs[:reranker_top_n]]
            reranker_used = True

    # Kontext NACH Reranking speichern
    kontext_nach = "\n---\n".join(
        f"[{d.metadata.get('source', '?')}]\n{d.page_content}" for d in docs
    )

    # 3. Router
    if router_active and ranked_docs:
        folder_profile_map = cfg.get("router", {}).get("folder_profile_map", {})
        profiles           = cfg.get("profiles", {})
        system_prompts     = cfg.get("system_prompts", {})
        fallback_profile   = cfg.get("router", {}).get("fallback_profile", "persoenlich")

        profil_name, profil_config = get_profile(ranked_docs[:reranker_top_n], folder_profile_map, profiles, fallback_profile)
        params = apply_profile(profil_config, system_prompts)

        llm_model     = params["llm_model"]
        temperature   = params["temperature"]
        system_prompt = params["system_prompt"]
        thinking      = params["thinking"]
        router_profil = profil_name

        print(f"  \U0001f916 LLM: {llm_model} | thinking: {thinking} | t={temperature}")

    # 4. Kontext + Prompt
    context = "\n\n".join([doc.page_content for doc in docs])
    quelldateien = list({doc.metadata.get("source", "?") for doc in docs})

    lang_instruction = f"Answer in the language with ISO code '{lang}'."
    print(f"  \U0001f5e3\ufe0f  Sprach-Anweisung: {lang_instruction}")

    prompt = f"""{system_prompt}

Heute ist: {now}

Kontext:
{context}

Frage: {question}

WICHTIG: {lang_instruction}
Antwort:"""

    # 5. Ollama
    options = {"temperature": temperature, "num_ctx": num_ctx}
    if thinking:
        options["thinking"] = True

    payload = {
        "model":      llm_model,
        "prompt":     prompt,
        "stream":     False,
        "keep_alive": keep_alive,
        "options":    options,
    }

    start = time.time()
    response = requests.post(OLLAMA_URL, json=payload, timeout=120)
    response.raise_for_status()
    wall_time = round(time.time() - start, 2)

    data = response.json()
    eval_count    = data.get("eval_count", 0)
    eval_duration = data.get("eval_duration", 1)
    tok_per_sec   = round(eval_count / eval_duration * 1e9, 1) if eval_duration > 0 else 0.0

    return {
        "answer":                data.get("response", "").strip(),
        "tok_per_sec":           tok_per_sec,
        "antwortzeit_sek":       wall_time,
        "tokens_generiert":      eval_count,
        "quelldateien":          quelldateien,
        "llm_model":             llm_model,
        "embedding_model":       EMBEDDING_MODEL,
        "reranker_used":         reranker_used,
        "chunks_gefunden":       chunks_gefunden,
        "chunks_nach_reranking": len(docs),
        "router_profil":         router_profil,
        "thinking":              thinking,
        "rewritten_query":       rewritten_query,
        "kontext_vor_reranking":  kontext_vor,
        "kontext_nach_reranking": kontext_nach,
        "chunk_scores":           chunk_scores,
    }



# ── Retrieval Debug ───────────────────────────────────────────────
def debug_retrieval(question):
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)
    top_k = load_config()["retrieval"]["top_k"]
    docs = db.similarity_search(question, k=top_k)
    print("\n🔍 DEBUG – Gefundene Chunks:")
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "?")
        print(f"\n{i}. {source}")
        print(doc.page_content[:150])
        print("---")


# ── Speicher-Logik ────────────────────────────────────────────────
def worth_saving(question):
    q_lower = question.lower()
    return not any(phrase in q_lower for phrase in UNWICHTIG)


def susi_evaluates(question, answer):
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


def get_suggestions(question, answer):
    combined = (question + " " + answer).lower()
    scores = {
        folder: sum(1 for kw in keywords if kw in combined)
        for folder, keywords in TOPIC_KEYWORDS.items()
    }
    top2 = sorted((f for f in scores if scores[f] > 0), key=lambda f: scores[f], reverse=True)[:2]
    return top2 if top2 else ["persoenlich/"]


def create_summary(question, answer, folder=""):
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


def save_to_susipedia(question, answer, folder):
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
        print(f"  ✅ Erweitert: {filepath}")
    else:
        title = folder.rstrip("/").split("/")[-1].capitalize()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n{new_section}")
        print(f"  ✅ Neu erstellt: {filepath}")

    print("  🔄 SUSIpedia wird aktualisiert...")
    subprocess.run(["python", "rag/ingest.py"], capture_output=True)
    print("  🎉 SUSIpedia aktualisiert!")


def show_save_prompt(question, answer):
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


# ── CLI ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🤖 SUSI ist bereit! (Embed: {EMBEDDING_MODEL} | Reranker: {RERANKER_MODEL})")
    print("   exit zum Beenden\n")

    while True:
        question = input("Du: ")
        if question.lower() == "exit":
            break

        result = ask_susi(question)
        profil_info   = f"Profil: {result['router_profil']}"
        thinking_info = " | 🧠 thinking" if result["thinking"] else ""
        print(f"\nSUSI: {result['answer']}")
        print(f"      ⚡ {result['tok_per_sec']} tok/s · {result['tokens_generiert']} Tokens · {result['antwortzeit_sek']}s · {profil_info}{thinking_info}\n")

        if worth_saving(question):
            if susi_evaluates(question, result["answer"]):
                show_save_prompt(question, result["answer"])