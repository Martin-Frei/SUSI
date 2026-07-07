# SUSI — Projekttagebuch
Datum: 2026-06-26
Status: aktiv
Kategorie: projekte

## Entstehung — SUSI Projekt

SUSI wurde am 20. März 2026 von Martin Freimuth ins Leben gerufen. Der Name steht für Selbständige Und Schlaue Intelligenzbestie. SUSI läuft vollständig lokal auf Martins Windows PC mit einem Ryzen 9 5900X, 32GB RAM und einer RTX 4070 mit 12 GB VRAM. Eine RTX 3090 mit 24GB VRAM ist als Erweiterung geplant.

## Tech Stack — SUSI Projekt

SUSI basiert auf einem mehrstufigen RAG-Stack. Als Embeddings dient BAAI/bge-m3 mit 1024 Dimensionen. Als Reranker läuft BAAI/bge-reranker-v2-m3. ChromaDB dient als Vektordatenbank mit einer Collection namens langchain. LangChain orchestriert die Pipeline. Django mit HTMX bildet das Web-Frontend auf Port 8008. Ollama läuft als lokaler LLM-Server. Die LLMs sind qwen2.5-coder:7b für technische Fragen, llama3.1:8b für Lerninhalte und qwen2.5:7b für persönliche Themen. Die gesamte Infrastruktur läuft lokal ohne Cloud-Abhängigkeiten, vollständig DSGVO-konform.

## Query Pipeline — SUSI Projekt

Die Query-Pipeline läuft in sechs Stufen. Zuerst erkennt detect_language() die Sprache der Frage via LLM-Call mit ISO 639-1 Code. Dann schreibt rewrite_query() die Frage um und löst Coreferences auf basierend auf den letzten zwei Frage-Antwort-Paaren aus der Chat-History. ChromaDB retrievet die top 7-9 ähnlichsten Chunks via bge-m3. Der bge-reranker-v2-m3 bewertet die Chunks und behält die besten 3-5. Der Router wählt basierend auf Chunk-Herkunft und Reranker-Score-Voting das passende Profil und LLM. Das LLM generiert die Antwort mit einer Sprachanweisung direkt vor dem Antwort-Token.

## Router-Profile — SUSI Projekt

SUSI verwendet fünf Router-Profile. Das susi-Profil nutzt qwen2.5-coder:7b mit top_k=7 und top_n=3 für SUSI-Eigendokumentation. Das projekte-Profil nutzt qwen2.5-coder:7b für Code-Projekte. Das lernen-Profil nutzt llama3.1:8b mit top_k=9 und top_n=5 für Lernmaterial. Das persoenlich-Profil nutzt qwen2.5:7b für persönliche Themen und dient gleichzeitig als Fallback wenn alle Reranker-Scores unter 0.01 liegen. Das technik-Profil nutzt qwen2.5-coder:7b für Hardware und Tools.

## Meilensteine — SUSI Projekt

Am 20. März 2026 wurde die Grundlage gelegt: Ollama installiert, Django-Projekt angelegt, ChromaDB und LangChain eingerichtet, SUSIpedia-Struktur aufgebaut. RAG funktionierte beim ersten Versuch. Im April und Mai 2026 wurde das Embedding-Modell von nomic-embed-text auf bge-m3 gewechselt was die Retrieval Hit Rate von 36 Prozent auf 91 Prozent verbesserte. Im Juni 2026 wurde der retrieval-getriebene Router implementiert, Query Rewriting mit Chat-History eingebaut, LLM-basierte Spracherkennung ergänzt und eine vollständige dreistufige Eval-Pipeline aufgebaut.

## Evaluation — SUSI Projekt

Die Evaluation läuft in drei Stufen. Stufe 1 ist grid_run.py der SUSI-Antworten für Parameterkombinationen generiert. Stufe 2 ist auto_scorer.py der regelbasiert mit ROUGE-L und BERTScore bewertet. Stufe 3 ist ragas_scorer.py der die Grauzone semantisch mit RAGAS Faithfulness und Answer Relevancy bewertet und optional einen Haiku-Judge für verbleibende unklare Einträge aufruft.

Lauf D mit 800 Runs (qwen2.5-coder:7b + llama3.1:8b) ergab nach vollständiger Bewertung mit RAGAS und Haiku Judge eine Gesamt-Korrektheit von 97.1 Prozent. Lauf E mit 586 Runs (qwen3:8b mit thinking=True vs thinking=False) ergab 98.3 Prozent ohne messbaren Unterschied zwischen thinking=True (1.972) und thinking=False (1.958).

## Geplante Features — SUSI Projekt

Kurzfristig geplant sind der HitL Queue Workflow für menschlich geprüfte Wissensergänzungen, ein Session-Summary Button im Frontend und Lauf F als End-to-End Router-Evaluation der kompletten Live-Pipeline. Mittelfristig sind eine Britannica API Integration mit neuem Wissensprofil, PDF-RAG für temporäre Dokumente und eine dynamische num_ctx Berechnung geplant. Langfristig sind Gesichtserkennung via Raspberry Pi, Sprachsteuerung via Whisper und eine Home Assistant Integration vorgesehen.

## Entwicklungsstufen — SUSI Projekt

SUSI entwickelt sich in drei Stufen. Stufe 1 ist der Coding und Knowledge Assistent der aktuell aktiv ist. Stufe 2 ist der physische Assistent mit Raspberry Pi der als nächstes folgt. Stufe 3 ist die Vision des persönlichen Lebensassistenten der vollständig autonom agiert.

## **Stand 2026-06-26**