# rag/keywords.py
# Statische Daten & Listen für die CLI-Speicherlogik.
#
# TOPIC_KEYWORDS:  Ordner → Keyword-Mapping für Speicher-Vorschläge.
#                  Genutzt von utils.get_suggestions().
# UNWICHTIG:       Phrasen die keinen Speicher-Dialog auslösen sollen.
#                  Genutzt von utils.worth_saving().

TOPIC_KEYWORDS = {
    "hobbys/tanzen":        ["tanz", "walzer", "salsa", "bachata", "kizomba",
                             "boogie", "rumba", "jive", "samba"],
    "hobbys/musik":         ["musik", "song", "metal", "klassik", "playlist"],
    "coding/stockpredict":  ["stockpredict", "lstm", "xgboost", "trading",
                             "pipeline", "backtest"],
    "coding/houseofstocks": ["houseofstocks", "django", "apscheduler", "allauth"],
    "coding/gmm":           ["gmm", "global market mood", "marketmood", "vader",
                             "finbert", "sentiment", "rss", "klassifikation",
                             "deepseek", "pgvector", "feeds", "artikel", "topic",
                             "geopolitics"],
    "coding/susi":          ["susi", "rag", "chromadb", "langchain", "ollama"],
    "coding/portfolio":     ["portfolio", "secret lab", "martin-freimuth"],
    "job/bewerbungen":      ["bewerbung", "firma", "stelle", "job", "arbeit",
                             "gehalt"],
    "finanzen/trading":     ["kapital", "geld", "erbschaft", "aktien", "rendite"],
    "wohnen/suche":         ["wohnung", "miete", "rosenheim", "zimmer",
                             "besichtigung"],
    "familie/sohn":         ["sohn", "kind", "borderline"],
    "persoenlich/":         ["gefühl", "gedanke", "reflexion", "trennung",
                             "beziehung"],
    "technik/":             ["raspberry", "arduino", "whisper", "home assistant"],
}

UNWICHTIG = [
    "wie spät", "datum", "hallo", "guten morgen", "guten abend",
    "danke", "tschüss", "ok", "super", "gut", "was ist die",
]