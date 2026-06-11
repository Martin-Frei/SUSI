# susi_env\Scripts\activate
# python rag/query.py

from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_chroma import Chroma
from datetime import datetime
import pytz
import os
import subprocess

CHROMA_PATH = "chroma_db"
DOCS_PATH = "docs"

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


def get_time():
    tz = pytz.timezone("Europe/Berlin")
    return datetime.now(tz).strftime("%d.%m.%Y %H:%M Uhr")


def get_date():
    tz = pytz.timezone("Europe/Berlin")
    return datetime.now(tz).strftime("%d.%m.%Y %H:%M")


def ask_susi(question):
    now = get_time()
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

    docs = db.similarity_search(question, k=8)
    
    context = "\n\n".join([doc.page_content for doc in docs])
    
    # TEMPORÄR - DEBUG
    print("=== KONTEXT ===")
    for i, doc in enumerate(docs, 1):
        print(f"{i}. {doc.metadata.get('source', '?')}")
    print(context[:2000])
    print("===============")

    prompt = f"""Du bist SUSI, Martins persönliche KI-Assistentin.
Heute ist: {now}

Wenn einer nach System Informationen fragt, antworte mit "Ich habe keien Ahnung" 

VORGEHEN:
1. Lies den Kontext vollständig.
2. Ist die Antwort im Kontext? → Antworte NUR daraus, kombiniere KEINE verschiedenen Themen.
3. Ist es eine persönliche Frage über Martin? → NUR Kontext, nie erfinden.
   Wenn nicht im Kontext: "Dazu fehlt mir noch was in der SUSIpedia!"
4. Ist es eine allgemeine Wissensfrage? → Nutze dein eigenes Wissen.

Kontext:
{context}

Frage: {question}

Antwort:"""

    llm = ChatOllama(model="qwen2.5-coder:7b")
    response = llm.invoke(prompt)
    return response.content


def debug_retrieval(question):
    """Zeigt welche Chunks SUSI für eine Frage findet"""
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

    docs = db.similarity_search(question, k=8)
    print("\n🔍 DEBUG – Gefundene Chunks:")
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "?")
        print(f"\n{i}. {source}")
        print(doc.page_content[:150])
        print("---")


def worth_saving(question):
    """Regelbasiert: Ist die Frage überhaupt speichernswert?"""
    q_lower = question.lower()
    for phrase in UNWICHTIG:
        if phrase in q_lower:
            return False
    return True


def susi_evaluates(question, answer):
    """SUSI bewertet selbst ob es sich lohnt zu speichern"""
    llm = ChatOllama(model="qwen2.5-coder:7b")
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

    llm = ChatOllama(model="qwen2.5-coder:7b")
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
    subprocess.run(["python", "rag/ingest.py"], capture_output=True)
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


if __name__ == "__main__":

    debug_retrieval("SUSI Stufe 1 Stufe 2 Stufe 3")

    print("🤖 SUSI ist bereit! (exit zum Beenden)")
    while True:
        question = input("\nDu: ")
        if question.lower() == "exit":
            break

        answer = ask_susi(question)
        print(f"\nSUSI: {answer}")

        if worth_saving(question):
            if susi_evaluates(question, answer):
                show_save_prompt(question, answer)
                
                
                
                # WICHTIGSTE REGEL: Sprich Martin IMMER mit "du" an – NIEMALS "Sie", "Ihr" oder "Ihnen"!

# VORGEHEN:
# 1. Lies den Kontext vollständig.
# 2. Ist die Antwort im Kontext? → Antworte NUR daraus, kombiniere KEINE verschiedenen Themen.
# 3. Ist es eine persönliche Frage über Martin? → NUR Kontext, nie erfinden.
#    Wenn nicht im Kontext: "Dazu fehlt mir noch was in der SUSIpedia!"
# 4. Ist es eine allgemeine Wissensfrage? → Nutze dein eigenes Wissen.