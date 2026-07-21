# SUSI — Kapitel 08b — Infrastruktur & Tooling
Datum: 2026-07-21
Status: aktiv
Zeitraum: 12. Juni – 21. Juli 2026

---

## Kapitel 08b — Wie ist SUSI gebaut?

Dieses Kapitel beschreibt die Infrastruktur hinter der Pipeline: zentrale Konfiguration, Chat-Persistenz, Frontend, SUSIpedia-Umstrukturierung, Chunking-Strategie, Code-Architektur und Diagnose-Tools.

→ *Pipeline-Kernkomponenten: [susi_08_produktivbetrieb_pipeline.md](susi_08_produktivbetrieb_pipeline.md)*
→ *Evaluierung und Optimierung: [susi_08_produktivbetrieb_evaluation.md](susi_08_produktivbetrieb_evaluation.md)*

---

## Single Source of Truth — susi_config.yaml

Die gesamte SUSI-Konfiguration wird zentral in `rag/susi_config.yaml` verwaltet. Ingest, Query und Views lesen alle Parameter aus dieser einzigen Datei — keine hardcodierten Werte mehr im Code. Modellwechsel, Chunk-Größen oder Prompt-Änderungen sind ein einziger Edit in einer Datei. Der gleichzeitige Wechsel von LangChain ChatOllama auf die direkte Ollama REST API brachte tok/s-Metriken zurück, die vorher nicht verfügbar waren.

### susi_config.yaml — Kernparameter

Die Retrieval-Sektion definiert `bge-m3` als Embedding-Modell, `top_k: 5` und den `similarity`-Algorithmus. Die Generation nutzt `qwen2.5-coder:7b` bei `temperature: 0.0` und `num_ctx: 4096`. Der Reranker ist aktiv mit `BAAI/bge-reranker-v2-m3` und `top_n: 3`. Die sechs Router-Profile (`susi`, `projekte`, `lernen`, `persoenlich`, `technik`, `wissen`) überschreiben jeweils LLM, top_k, top_n und temperature pro Kategorie.

---

## Chat-History in SQLite (25.06.)

Das Problem: Chatverlauf war nur in der Django-Session — bei Ollama-Crashes oder Browser-Schließen verloren.

### Implementierung

Die Django-Models `Chat`, `Message` und `QueueItem` persistieren den gesamten Chatverlauf in SQLite. Die Session speichert nur noch die `active_chat_id`, alle Messages kommen aus der DB. Die Chat-Sidebar zeigt alle gespeicherten Chats. Jede SUSI-Antwort hat einen HitL-Queue-Button — per Klick landet die Antwort als `QueueItem` in der Datenbank für späteres Review.

Der Rewriter bekommt die letzten zwei Q/A-Paare aus der DB statt aus der Session. Antworten werden auf 200 Zeichen gekürzt um den Rewriter-Kontext klein zu halten.

---

## Frontend-Entwicklung (12.06.–07.07.)

### Einstellungs-Sidebar (12.06.)

Slider für LLM, top_k, temperature, num_ctx und System-Prompt erlauben die direkte Konfiguration aus dem Frontend. Die Werte werden in die Django-Session geschrieben.

### Retrieval-Info Sidebar (12.06.)

Nach jeder Frage wird live angezeigt: Anzahl gefundener Chunks, Anzahl nach Reranking und die Quelldateien. Der HTMX Out-of-Band Swap erfolgt ohne Extra-Request.

### tok/s-Anzeige (12.06.)

Unter jeder Antwort erscheinen Metriken wie `⚡ 84.2 tok/s · 97 Tokens · 5.42s · 🔁 reranked`. Diese Daten sind verfügbar durch den Wechsel auf die direkte Ollama REST API.

### SUSI-Icon und lokale Fonts (20.06.)

Das SUSI-Icon ist im Superman-Schild-Stil gestaltet: Gold (#9A7000) auf Dunkel (#12122a), großes S als Serif-Buchstabe, ViewBox eng gecroppt für Favicon-Nutzung. Google Fonts wurden durch lokale `@font-face`-Deklarationen ersetzt. JetBrains Mono in den Gewichten 300, 400 und 600 sowie Syne in 400, 700 und 800 werden lokal geladen — kein externer Request, vollständig DSGVO-konform.

### AUTO / MANUELL / CODING Toggle (Juni 2026)

Ein Modus-Toggle im Chat-Header erlaubt das Umschalten zwischen drei Betriebsmodi. Der `mode`-Parameter fließt von `views.py` durch `ask_susi()` bis zum `agent_datum`-Guard. AUTO ist der Standard-Produktivmodus. MANUELL soll Router-Bypass mit Session-Overrides liefern. Bekannter Bug: die Session-Werte (LLM, top_k, temp, num_ctx, Prompt) werden zwar geschrieben, aber `ask_susi()` wendet sie nicht an — der Router läuft weiterhin. Fix ist in Arbeit. CODING ist definiert aber noch nicht vollständig spezifiziert.

---

## SUSIpedia-Umstrukturierung (20.06.)

Die SUSIpedia wurde am 20. Juni neu strukturiert. Der Ordner `docs/susi/` wurde neu angelegt für die SUSI-eigene Dokumentation, die vorher in `coding/susi/` und im Root-Verzeichnis verstreut war. Die übrigen Ordner blieben erhalten oder wurden angepasst: `coding/` (GMM, HouseOfStocks, StockPredict, Portfolio), `projekte/` (Projektbeschreibungen und Roadmaps), `lernen/` (AI, ML, RAG, Python, JavaScript, DevOps), `job/` (Bewerbung, CV, LinkedIn), `technik/` (Hardware, Tools, Setup), `martin/` (persönliches Profil), `familie/` und `hobbys/`.

Nach der Umstrukturierung wurden alle Dateien neu indexiert: 617 Chunks in ChromaDB. Die veraltete `tree.md` wurde gelöscht. Am 06.07. wurden zwei Stale-Duplikate entfernt: `docs/lernen/susi/susiuebersicht.md` und `docs/technik/susi_grenzen_und_roadmap.md`.

---

## Ingest-Umbau — split_by_headings + _split_oversized (17.–21.07.)

### split_by_headings (17.07.)

`RecursiveCharacterTextSplitter` (chunk_size=1000, chunk_overlap=50) wurde durch `split_by_headings()` in `rag/ingest.py` ersetzt. Das Problem: wenn mehrere `##`-Sektionen zusammen unter 1000 Zeichen waren, packte der alte Splitter sie in einen Chunk. `martin_soehne.md` (~600 Zeichen) wurde ein Chunk mit Philip und Jakob — Zweig 2 konnte die Entitäten nicht trennen.

Der neue Splitter splittet exakt an `##`-Headings. Jedes Heading ergibt genau einen Chunk. Der Datei-Header (Titel, Datum, Status, Kategorie) wird in jeden Chunk injiziert — self-contained. Der `## **Stand DD.MM.YYYY**` Footer wird gefiltert. Fallback: Dateien ohne `##` werden als ein Chunk behandelt. Ergebnis: 617 → 1128 Chunks, `martin_soehne.md` von 1 auf 3 Chunks (Übersicht, Philip, Jakob).

### _split_oversized (21.07.)

Drei Dateien in `docs/job/` waren nicht gechunkt (`SKILL_CV.md` 14.656 chars, `SKILL_Anschreiben.md` 7.407 chars) und ein Wikipedia-Artikel ohne `##`-Headings hatte 29.418 chars als ein Chunk. Der CrossEncoder skaliert quadratisch mit Sequenzlänge — Reranking dauerte bei diesen Chunks 100–130s statt 3–5s.

`_split_oversized()` ist jetzt ein Fallback in `split_by_headings()`: Chunks über 1500 chars werden an Absatzgrenzen (`\n\n`) aufgebrochen, einzelne Absätze die immer noch zu groß sind an Satzgrenzen (`. `). Header und Heading-Zeile werden in jeden Sub-Chunk injiziert. `max_chunk_chars=1500` als Default — empirisch getestet: 500–1500 chars kein messbarer Performance-Unterschied beim Reranker auf CPU. Aktueller Zustand ChromaDB: 1176 Chunks, Ø 641 chars, Min 125, Max 1497, übergroß (>1500): 0.

---

## Wikipedia-Heading-Konvertierung (21.07.)

`rag/agent_pedia.py` bekommt `_convert_wiki_headings(text, title)`: konvertiert Wikipedias `==`/`===`/`====` Syntax zu `## Title — Heading` (SUSIpedia-konform). Filtert Non-Content-Sektionen (Literatur, Weblinks, Einzelnachweise, Siehe auch). Ohne diese Konvertierung packte `to_susipedia_md()` den gesamten Artikeltext unter eine einzige `## Übersicht` — bei Python 29.418 chars als ein Chunk. Bekannter Restzustand: Sub-Headings unter gefilterten Sektionen rutschen durch — betrifft nur Link-Listen ohne RAG-Wert.

---

## query.py Refactoring — 1 Datei → 5 Module (17.07.)

`rag/query.py` (861 Zeilen) wurde in fünf Module aufgeteilt. Die Signatur von `ask_susi()` und das Return-Dict blieben identisch — `views.py`, `grid_run.py` und das Frontend brauchten keine Änderung.

`rag/config.py` enthält `load_config()` und alle statischen Konstanten (`OLLAMA_URL`, `CHROMA_PATH`, `EMBEDDING_MODEL` etc.). `rag/keywords.py` enthält `TOPIC_KEYWORDS` und `UNWICHTIG`. `rag/llm_client.py` enthält `detect_language()`, `rewrite_query()`, `create_summary()` und `susi_evaluates()`. `rag/utils.py` enthält Zeithilfen, `worth_saving()`, `save_to_susipedia()` und `show_save_prompt()`. `rag/query.py` behält `get_reranker()`, `ask_susi()`, `debug_retrieval()` und die CLI.

Zentrale Verbesserung: `ask_susi_eval()` war eine 200-Zeilen-Kopie von `ask_susi()` mit drei Extra-Feldern. Diese Duplizierung hatte am 27.06. den Double-Rewriting-Bug verursacht (→ Grenzerfahrung 6). `ask_susi()` bekommt stattdessen `eval_mode: bool = False`. `ask_susi_eval()` existiert als dünner Wrapper für Rückwärtskompatibilität. Import-Abhängigkeiten sind geradlinig von config → keywords → llm_client → utils → query — keine zirkulären Imports.

---

## chunk_audit.py — ChromaDB-Diagnose (21.07.)

`tools/evaluation/chunk_audit.py` liest ChromaDB und zeigt alle Chunks mit Größen. Aufruf: `python tools/evaluation/chunk_audit.py --only-oversized` für Problemfälle, `--top 20` für die größten, `--limit 1500` für anderen Schwellenwert. Zeigt übergroße Chunks mit Faktor/Quelle/Preview und Statistik pro Ordner.

---

## GitHub — Build in Public (Stand Juli 2026)

Das Repository `github.com/Martin-Frei/SUSI` ist öffentlich. In 14 Tagen: 33 Unique Cloners, Traffic primär über LinkedIn-Direktlinks. Markus hat das Repo geforkt und trägt als Community-Contributor bei. Sechs saubere Commits am 07.07. im Conventional-Commit-Format (`feat/refactor/config/docs`). `Test_query.py` in `.gitignore` aufgenommen.

---

## Stand: Juli 2026 · Martin Freimuth

→ Zurück zur Übersicht: `susi_00_übersicht.md`
→ Zurück: `susi_08_produktivbetrieb_pipeline.md`
→ Weiter: `susi_08_produktivbetrieb_evaluation.md`