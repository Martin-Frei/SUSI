# susi_env\Scripts\activate
# python rag/query.py

from datetime import datetime
import pytz
import os
import re

CHROMA_PATH = "chroma_db"
DOCS_PATH = "docs"
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "susi_config.yaml")


def _load_config():
    """Load susi_config.yaml. Raises if missing/broken (callers decide fallback)."""
    import yaml
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


EMBED_MODEL = "nomic-embed-text"
DEFAULT_LLM = "qwen2.5-coder:7b"

# Ordner-Struktur für Vorschläge
TOPIC_KEYWORDS = {
    "hobbys/tanzen": [
        "tanz", "walzer", "salsa", "bachata", "kizomba",
        "boogie", "rumba", "jive", "samba",
    ],
    "hobbys/musik": ["musik", "song", "metal", "klassik", "playlist"],
    "coding/stockpredict": [
        "stockpredict", "lstm", "xgboost", "trading", "pipeline", "backtest",
    ],
    "coding/houseofstocks": ["houseofstocks", "django", "apscheduler", "allauth"],
    "coding/gmm": [
        "gmm", "global market mood", "marketmood", "vader", "finbert",
        "sentiment", "rss", "klassifikation", "deepseek", "pgvector",
        "feeds", "artikel", "topic", "geopolitics",
    ],
    "coding/susi": ["susi", "rag", "chromadb", "langchain", "ollama"],
    "coding/portfolio": ["portfolio", "secret lab", "martin-freimuth"],
    "job/bewerbungen": ["bewerbung", "firma", "stelle", "job", "arbeit", "gehalt"],
    "finanzen/trading": ["kapital", "geld", "erbschaft", "aktien", "rendite"],
    "wohnen/suche": ["wohnung", "miete", "rosenheim", "zimmer", "besichtigung"],
    "familie/sohn": ["sohn", "kind", "borderline"],
    "persoenlich/": ["gefühl", "gedanke", "reflexion", "trennung", "beziehung"],
    "technik/": ["raspberry", "arduino", "whisper", "home assistant"],
}

# Unwichtige Fragen – kein Speicher-Prompt
UNWICHTIG = [
    "wie spät", "datum", "hallo", "guten morgen", "guten abend",
    "danke", "tschüss", "ok", "super", "gut", "was ist die",
]


_DEFAULT_SYSTEM_PROMPTS = {
    "susi_standard": (
        "Du bist SUSI, Martins persönliche KI-Assistentin.\n"
        "Heute ist: {now}\n\n"
        "Wenn jemand nach System-Informationen fragt, antworte mit "
        "\"Ich habe keine Ahnung\".\n\n"
        "VORGEHEN:\n"
        "1. Lies den Kontext vollständig.\n"
        "2. Ist die Antwort im Kontext? -> Antworte NUR daraus, kombiniere KEINE "
        "verschiedenen Themen.\n"
        "3. Ist es eine persönliche Frage über Martin? -> NUR Kontext, nie erfinden.\n"
        "   Wenn nicht im Kontext: \"Dazu fehlt mir noch was in der SUSIpedia!\"\n"
        "4. Ist es eine allgemeine Wissensfrage? -> Nutze dein eigenes Wissen."
    ),
}


def _load_system_prompts():
    """Prompt name -> text, from the YAML; falls back to the built-in default."""
    try:
        cfg = _load_config()
        loaded = {p["name"]: p["text"] for p in cfg.get("prompts", [])}
        return loaded or dict(_DEFAULT_SYSTEM_PROMPTS)
    except Exception:
        return dict(_DEFAULT_SYSTEM_PROMPTS)


SYSTEM_PROMPTS = _load_system_prompts()


def build_prompt(question, context, now, system_prompt="susi_standard"):
    """Assemble the full LLM prompt. Pure function, no side effects.
    Unknown system_prompt keys fall back to 'susi_standard'."""
    instructions = SYSTEM_PROMPTS.get(system_prompt, SYSTEM_PROMPTS["susi_standard"])
    instructions = instructions.replace("{now}", now)
    return (
        f"{instructions}\n\n"
        f"Kontext:\n{context}\n\n"
        f"Frage: {question}\n\n"
        f"Antwort:"
    )


def get_frontend_config():
    """Config consumed by the web sidebar. Reads susi_config.yaml."""
    cfg = _load_config()
    return {
        "llm_options":         cfg["llm_options"],
        "prompt_options":      [{"name": p["name"], "label": p["label"]} for p in cfg["prompts"]],
        "top_k_min":           cfg["top_k_min"],
        "top_k_max":           cfg["top_k_max"],
        "top_k_default":       cfg["top_k_default"],
        "temperature_min":     cfg["temperature_min"],
        "temperature_max":     cfg["temperature_max"],
        "temperature_step":    cfg["temperature_step"],
        "temperature_default": cfg["temperature_default"],
        "prompt_default":      cfg["prompt_default"],
        "llm_default":         cfg["llm_default"],
    }


_DB_CACHE = {}


def _get_db(embed_model=EMBED_MODEL):
    """Return a cached Chroma handle for the given embedding model.
    Heavy imports happen here so the module imports without langchain/chromadb."""
    from langchain_ollama import OllamaEmbeddings
    from langchain_chroma import Chroma
    if embed_model not in _DB_CACHE:
        embeddings = OllamaEmbeddings(model=embed_model)
        _DB_CACHE[embed_model] = Chroma(
            persist_directory=CHROMA_PATH, embedding_function=embeddings
        )
    return _DB_CACHE[embed_model]


def _chat(model=DEFAULT_LLM, temperature=0.0):
    """Return a ChatOllama instance (lazy import)."""
    from langchain_ollama import ChatOllama
    return ChatOllama(model=model, temperature=temperature)


def get_time():
    tz = pytz.timezone("Europe/Berlin")
    return datetime.now(tz).strftime("%d.%m.%Y %H:%M Uhr")


def get_date():
    tz = pytz.timezone("Europe/Berlin")
    return datetime.now(tz).strftime("%d.%m.%Y %H:%M")


def ask_susi(question, *, top_k=8, temperature=0.0,
             system_prompt="susi_standard", llm_model=DEFAULT_LLM):
    now = get_time()
    db = _get_db()
    docs = db.similarity_search(question, k=top_k)
    context = "\n\n".join(doc.page_content for doc in docs)
    prompt = build_prompt(question, context, now, system_prompt)
    return _chat(model=llm_model, temperature=temperature).invoke(prompt).content


def debug_retrieval(question):
    """Zeigt welche Chunks SUSI für eine Frage findet"""
    db = _get_db()

    docs = db.similarity_search(question, k=8)
    print("\n🔍 DEBUG – Gefundene Chunks:")
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "?")
        print(f"\n{i}. {source}")
        print(doc.page_content[:150])
        print("---")


def worth_saving(question):
    """True if the question is worth offering to save. Matches UNWICHTIG phrases
    on WORD BOUNDARIES so 'gut' no longer matches inside 'gute' etc."""
    q = question.lower().strip()
    for phrase in UNWICHTIG:
        if re.search(r"\b" + re.escape(phrase) + r"\b", q):
            return False
    return True


def susi_evaluates(question, answer):
    """SUSI bewertet selbst ob es sich lohnt zu speichern"""
    llm = _chat()
    prompt = f"""Bewerte ob diese Konversation wichtige neue Information enthält
die es wert ist dauerhaft gespeichert zu werden.
Antworte NUR mit: JA oder NEIN

Frage: {question}
Antwort: {answer}"""

    response = llm.invoke(prompt)
    return "JA" in response.content.upper()


def get_suggestions(question, answer):
    """Top 2 passende Ordner vorschlagen"""
    combined = (question + " " + answer).lower()
    scores = {}

    for folder, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > 0:
            scores[folder] = score

    top2 = sorted(scores, key=scores.get, reverse=True)[:2]
    return top2 if top2 else ["persoenlich/"]


def create_summary(question, answer, folder=""):
    """SUSI erstellt eine kompakte Zusammenfassung"""
    now = get_time()

    technical = ["coding", "technik", "lernen"]
    max_chars = 500 if any(t in folder for t in technical) else 300

    llm = _chat()
    prompt = f"""Du bist SUSI, Martins persönliche KI-Assistentin.
Heute ist: {now}

Erstelle eine kompakte Zusammenfassung dieses Gesprächs für die SUSIpedia.
Sprich Martin IMMER mit "du" an – NIEMALS "Sie", "Ihr" oder "Ihnen"!
Schreibe vollständige Sätze, KEINE Listen!
Maximal {max_chars} Zeichen.

Frage: {question}
Antwort: {answer}

Zusammenfassung:"""

    response = llm.invoke(prompt)
    summary = response.content.strip()

    if len(summary) > max_chars:
        summary = summary[:max_chars - 3] + "..."

    return summary


def save_to_susipedia(question, answer, folder):
    """Zusammenfassung in passende .md Datei speichern"""
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
    from rag.ingest import ingest_docs
    ingest_docs()
    print("  🎉 SUSIpedia aktualisiert!")


def show_save_prompt(question, answer):
    """Speicher-Dialog anzeigen"""
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


def main():
    print("🤖 SUSI ist bereit! (exit zum Beenden)")
    while True:
        question = input("\nDu: ")
        if question.lower() == "exit":
            break
        answer = ask_susi(question)
        print(f"\nSUSI: {answer}")
        if worth_saving(question) and susi_evaluates(question, answer):
            show_save_prompt(question, answer)


if __name__ == "__main__":
    main()
