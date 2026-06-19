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

# ── Config laden ──────────────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "susi_config.yaml")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

cfg = load_config()

CHROMA_PATH      = cfg["retrieval"]["chroma_path"]
DOCS_PATH        = cfg["paths"]["docs"]
EMBEDDING_MODEL  = cfg["retrieval"]["embedding_model"]
TOP_K            = cfg["retrieval"]["top_k"]
ALGORITHM        = cfg["retrieval"]["algorithm"]
LLM_MODEL        = cfg["generation"]["llm_model"]
TEMPERATURE      = cfg["generation"]["temperature"]
NUM_CTX          = cfg["generation"]["num_ctx"]
KEEP_ALIVE       = cfg["generation"]["keep_alive"]
PROMPT_NAME      = cfg["generation"]["system_prompt"]
SYSTEM_PROMPT    = cfg["system_prompts"][PROMPT_NAME]
OLLAMA_URL       = "http://localhost:11434/api/generate"

# ── Reranker ──────────────────────────────────────────────────────
_reranker_cfg    = cfg.get("reranker", {})
RERANKER_ACTIVE  = _reranker_cfg.get("active", False)
RERANKER_MODEL   = _reranker_cfg.get("model", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RERANKER_TOP_N   = _reranker_cfg.get("top_n", 3)

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


# ── Kern-Funktion ─────────────────────────────────────────────────
def ask_susi(question):
    """
    Stellt eine Frage an SUSI und gibt ein Dict zurück:
    {
        "answer":            str,
        "tok_per_sec":       float,
        "antwortzeit_sek":   float,
        "tokens_generiert":  int,
        "quelldateien":      list[str],
        "llm_model":         str,
        "embedding_model":   str,
    }
    """
    now = get_time()

    # Config frisch laden (damit Frontend-Änderungen sofort wirken)
    cfg = load_config()
    top_k       = cfg["retrieval"]["top_k"]
    algorithm   = cfg["retrieval"]["algorithm"]
    llm_model   = cfg["generation"]["llm_model"]
    temperature = cfg["generation"]["temperature"]
    num_ctx     = cfg["generation"]["num_ctx"]
    keep_alive  = cfg["generation"]["keep_alive"]
    prompt_name = cfg["generation"]["system_prompt"]
    system_prompt = cfg["system_prompts"][prompt_name]
    reranker_active = cfg.get("reranker", {}).get("active", False)
    reranker_top_n  = cfg.get("reranker", {}).get("top_n", 3)

    # 1. Retrieval
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

    if algorithm == "mmr":
        docs = db.max_marginal_relevance_search(question, k=top_k)
    else:
        docs = db.similarity_search(question, k=top_k)

    # 1b. Reranker (optional)
    chunks_gefunden = len(docs)
    reranker_used = False
    if reranker_active:
        reranker = get_reranker()
        if reranker:
            pairs = [(question, doc.page_content) for doc in docs]
            scores = reranker.predict(pairs)
            ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
            docs = [doc for _, doc in ranked[:reranker_top_n]]
            reranker_used = True
    chunks_nach_reranking = len(docs)

    context = "\n\n".join([doc.page_content for doc in docs])
    quelldateien = list({doc.metadata.get("source", "?") for doc in docs})

    # 2. Prompt bauen
    prompt = f"""{system_prompt}

Heute ist: {now}

Kontext:
{context}

Frage: {question}

Antwort:"""

    # 3. LLM via Ollama REST API (liefert tok/s Metriken)
    payload = {
        "model":      llm_model,
        "prompt":     prompt,
        "stream":     False,
        "keep_alive": keep_alive,
        "options": {
            "temperature": temperature,
            "num_ctx":     num_ctx,
        }
    }

    start = time.time()
    response = requests.post(OLLAMA_URL, json=payload, timeout=120)
    response.raise_for_status()
    wall_time = round(time.time() - start, 2)

    data = response.json()

    eval_count    = data.get("eval_count", 0)
    eval_duration = data.get("eval_duration", 1)   # Nanosekunden
    tok_per_sec   = round(eval_count / eval_duration * 1e9, 1) if eval_duration > 0 else 0.0

    return {
        "answer":           data.get("response", "").strip(),
        "tok_per_sec":      tok_per_sec,
        "antwortzeit_sek":  wall_time,
        "tokens_generiert": eval_count,
        "quelldateien":     quelldateien,
        "llm_model":        llm_model,
        "embedding_model":  EMBEDDING_MODEL,
        "reranker_used":         reranker_used,
        "chunks_gefunden":       chunks_gefunden,
        "chunks_nach_reranking": len(docs),
    }


# ── Retrieval Debug ───────────────────────────────────────────────
def debug_retrieval(question):
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)
    docs = db.similarity_search(question, k=TOP_K)
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
    top2 = sorted((f for f in scores if scores[f] > 0), key=scores.get, reverse=True)[:2]
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
    print(f"🤖 SUSI ist bereit! (LLM: {LLM_MODEL} | Embed: {EMBEDDING_MODEL})")
    print("   exit zum Beenden\n")

    while True:
        question = input("Du: ")
        if question.lower() == "exit":
            break

        result = ask_susi(question)
        print(f"\nSUSI: {result['answer']}")
        print(f"      ⚡ {result['tok_per_sec']} tok/s · {result['tokens_generiert']} Tokens · {result['antwortzeit_sek']}s\n")

        if worth_saving(question):
            if susi_evaluates(question, result["answer"]):
                show_save_prompt(question, result["answer"])