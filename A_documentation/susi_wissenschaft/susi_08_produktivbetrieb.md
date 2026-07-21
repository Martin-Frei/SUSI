# SUSI — Kapitel 08 — Vom evaluierten System zum produktiven Assistenten
Datum: 2026-07-21
Status: aktiv
Zeitraum: 12. Juni – 21. Juli 2026

---

## Kapitel 08 — Übergang in den Produktivbetrieb

Dieses Kapitel dokumentiert den Übergang von SUSI aus der Evaluierungsphase (Kapitel 00–07) in den aktiven Produktivbetrieb. Im Mittelpunkt stehen die zentrale Konfiguration via `susi_config.yaml`, die Reranker-Evolution, der retrieval-getriebene Router, Query Rewriting, Fallback-Profil, Chat-History in SQLite, die Tool-Use-Architektur mit `agent_datum` und `agent_britannica`, die Britannica-Integration als externe Wissensquelle, das Refactoring der Query-Pipeline in fünf Module, sowie die Chunking-Strategie mit `split_by_headings()` und `_split_oversized()`.

---

## Single Source of Truth — susi_config.yaml

Die gesamte SUSI-Konfiguration wird zentral in `rag/susi_config.yaml` verwaltet. Ingest, Query und Views lesen alle Parameter aus dieser einzigen Datei — keine hardcodierten Werte mehr im Code. Modellwechsel, Chunk-Größen oder Prompt-Änderungen sind ein einziger Edit in einer Datei. Der gleichzeitige Wechsel von LangChain ChatOllama auf die direkte Ollama REST API brachte tok/s-Metriken zurück, die vorher nicht verfügbar waren.

### susi_config.yaml — Kernparameter

Die Retrieval-Sektion definiert `bge-m3` als Embedding-Modell, `top_k: 5` und den `similarity`-Algorithmus. Die Generation nutzt `qwen2.5-coder:7b` bei `temperature: 0.0` und `num_ctx: 4096`. Der Reranker ist aktiv mit `BAAI/bge-reranker-v2-m3` und `top_n: 3`. Die fünf Router-Profile (`susi`, `projekte`, `lernen`, `persoenlich`, `technik`) überschreiben jeweils LLM, top_k, top_n und temperature pro Kategorie.

---

## Reranker-Evolution — ms-marco → amberoad → bge

Die Reranker-Entwicklung verlief in drei Stufen, jede mit klarer Lektion.

### Stufe 1 — ms-marco-MiniLM (12.06.)

Der erste eingesetzte Reranker war `cross-encoder/ms-marco-MiniLM-L-6-v2` mit etwa 90 MB, läuft auf CPU ohne VRAM-Verbrauch. Das grundlegende Problem war, dass das Modell ausschließlich auf Englisch trainiert ist und deutsche semantische Abweichungen nicht erkannte. Das Modell wurde nie formal evaluiert, aber früh als ungeeignet eingestuft.

### Stufe 2 — amberoad/bert-multilingual (18.06.)

Der Smoke Test ergab 59% Korrektheit mit Reranker gegenüber 100% ohne Reranker. Das Modell war damit aktiv schädlich — es warf gute Chunks weg und sortierte schlechte nach oben. Die Lektion: Ein schlechter Reranker ist schlimmer als gar kein Reranker.

### Stufe 3 — BAAI/bge-reranker-v2-m3 (18.06.)

Der Smoke Test ergab 97% Korrektheit. Das Modell stammt vom selben Team wie das Embedding-Modell `bge-m3`, beide harmonieren perfekt miteinander. Seitdem ist dieses Modell produktiv im Einsatz. Die Kernlektion: Der Reranker muss zum Embedding-Modell und zur Dokumentsprache passen. Vor jeder Produktivsetzung ist ein Smoke Test Pflicht. Die Baseline ohne Reranker ist immer besser als ein falscher Reranker.

Der direkte Vergleich zeigt das Ausmaß: `amberoad/bert-multilingual` erzielte ohne Reranker einen Ø Score von 2.94 bei 100% Korrektheit, mit Reranker nur Ø 1.75 bei 59% — ein katastrophaler Rückgang. `BAAI/bge-reranker-v2-m3` erzielte ohne Reranker Ø 3.00 bei 100% und mit Reranker Ø 2.91 bei 97% — ein minimal akzeptabler Trade-off.

---

## qwen vs. llama — empirisches Modellprofil

Am 12. Juni wurde derselbe Fragentyp mit beiden Modellen verglichen, das Ergebnis zeigt ein klares, stabiles Profil.

### qwen2.5-coder:7b — der Präzisions-Spezialist

`qwen2.5-coder:7b` produziert token-effiziente Antworten: 63 Tokens gegenüber 236 Tokens von llama für dieselbe Information. Das Modell beantwortet Faktenfragen kurz und präzise ohne Geschwätz, hält sich zuverlässig an die Sprache der Frage (getestet: Deutsch, Englisch, Französisch, Italienisch, Spanisch), läuft optimal bei `temperature: 0.0` und halluziniert bei Fakten weniger als llama.

### llama3.1:8b — der Analyst

`llama3.1:8b` verbindet Informationen aus mehreren Quellen bei Multi-Dokument-Fragen und liefert nuancierteres Reasoning bei persönlicher Reflexion. Das Modell ignoriert den Mehrsprachigkeits-Prompt und antwortet unabhängig von der Fragesprache immer auf Deutsch. `temperature: 0.3` ist für analytische Fragen besser geeignet.

### Temperature-Experiment (12.06.)

Dieselbe Frage bei `temperature: 0.0` ergab 63 Tokens, präzise und auf den Punkt. Bei `temperature: 1.0` entstanden 183 Tokens mit ausgeschmückter Formulierung und erhöhter Halluzinations-Tendenz. Das Fazit: `temperature: 0.0` ist der richtige Standard für SUSI als Wissensassistent.

---

## Router-Entwicklung — vom Plan zur Implementierung

Der SUSI-Router wurde in vier Phasen entwickelt, wobei Lauf C die Architekturentscheidung grundlegend beeinflusste.

### Phase 1 — Problem erkannt (12.06.)

Ein fixer Parameter-Satz für alle Fragen ist suboptimal. Die erste Idee war ein strukturbasierter Fragetyp-Router: Fragen mit „wie heißt", „wann", „welches" → qwen; Fragen mit „warum", „was bedeutet" → llama.

### Phase 2 — Konzept geplant (13.06.)

Drei Profile wurden konzipiert: A (Fakten), B (Analytisch), C (Mehrsprachig). Drei Implementierungsoptionen wurden bewertet: keyword-basiert (einfach, fragil), LLM-Klassifikator (genauer, aber Extra-Call nötig) und embedding-basiert (schnell, hoher Aufwand). Der Plan sah Option 1 als ersten Schritt vor.

### Phase 3 — Lauf C ändert die Architektur (18.06.)

Lauf C mit 5.860 Runs und 20 Parameterkombinationen ergab: Parameter-Unterschiede betragen maximal 0.07 Punkte — statistisch irrelevant. Die entscheidende Erkenntnis war, dass nicht die Frageformulierung die optimalen Parameter bestimmt, sondern die Kategorie der gefundenen Chunks. Die SUSIpedia-Ordnerstruktur ist der bessere Router als jedes Keyword-Matching.

### Phase 4 — Retrieval-getriebener Router implementiert (20.06.)

Der produktive Router funktioniert so: Die Frage geht in das Retrieval mit k=7, der Reranker sortiert die Top 3. Der Router analysiert die Herkunft der Chunks anhand der Ordnerpfade und summiert die Reranker-Scores pro Kategorie — jeder Chunk addiert seinen Score zu der Kategorie aus deren Ordner er stammt. Das Profil mit der höchsten Gesamtsumme gewinnt und bestimmt LLM sowie alle Parameter für die Antwortgenerierung.

### Router-Profile (Stand Juli 2026)

Das Profil `susi` gilt für den Ordner `docs/susi/` und nutzt `qwen2.5-coder:7b` mit top_k 7, top_n 3 und temperature 0.0. Das Profil `projekte` gilt für `docs/coding/` und `docs/projekte/` mit denselben Parametern. Das Profil `lernen` gilt für `docs/lernen/` und nutzt `llama3.1:8b` mit top_k 9, top_n 5 und temperature 0.3. Das Profil `persoenlich` gilt für `docs/martin/`, `docs/job/`, `docs/familie/` und `docs/hobbys/` mit `qwen2.5:7b`, top_k 5, top_n 3 und temperature 0.0. Das Profil `technik` gilt für `docs/technik/` mit `qwen2.5-coder:7b`, top_k 5, top_n 3 und temperature 0.0. Das Profil `wissen` gilt für `docs/wissen/` (Britannica- und Wikipedia-Artikel, seit 17.07.) und nutzt `llama3.1:8b` mit top_k 7, top_n 3 und temperature 0.1.

### Warum Retrieval-getrieben besser ist als Frage-basiert

Der retrieval-getriebene Ansatz ist robuster, weil er sich an der tatsächlichen Wissensbasis orientiert und nicht an Sprachmustern. Er ist selbst-konsistent, weil SUSI ihre eigene SUSIpedia-Struktur kennt. Er vermeidet Overfitting: neue Ordner werden automatisch einem Profil zugeordnet. Er benötigt keinen Extra-LLM-Call, weil die Reranker-Scores bereits vorhanden sind.

Das `thinking`-Flag ist in der Config und in `apply_profile()` für qwen3 vorbereitet. Bei einem Modellwechsel zu qwen3 genügt ein Eintrag in der Config — kein Code-Umbau nötig.

---

## Query Rewriting — Ich-Form und Coreference-Auflösung

Das Problem: Embedding-Modelle können keine Coreference auflösen. Die Frage „Ich bin Martin. Wo wohne ich?" findet nicht den richtigen Chunk, weil „ich" und „Martin" im Vektorraum nicht verknüpft sind.

### Implementierung (20.06.)

Ein LLM-Call mit demselben Modell, `num_ctx: 512` und `temperature: 0.0` schreibt die Frage vor dem Retrieval um. Aus „Ich bin Martin. Wo wohne ich?" wird „Martin Freimuth wo wohne ich?". ChromaDB sucht mit der umgeschriebenen Frage. An das Antwort-LLM geht die Original-Frage für eine natürliche Antwort. Ergänzt wird das durch `docs/martin/ich_bin_martin.md` mit zwei Chunks, die Selbstreferenz-Sätze enthalten.

### Design-Entscheidungen

Der Rewriter ist generisch gehalten ohne Overfitting auf Martin-spezifische Patterns, damit das System später auch für PDF-RAG-Nutzung geeignet ist. Ein Config-Flag `query_rewriting.active` erlaubt jederzeit die Deaktivierung. Als Fail-safe gibt die Funktion bei jedem Fehler immer die Original-Frage zurück.

### Fixes (21.06.)

Zwei Bugs wurden nach dem ersten Produktiveinsatz behoben. Das Sprachproblem: Der Rewriter schrieb umgeschriebene Fragen immer auf Deutsch, unabhängig von der Eingabesprache. Die Lösung war ein expliziter Prompt-Zusatz: „Schreibe IMMER in der gleichen Sprache wie die aktuelle Frage." Das Ablehnungsproblem: Der Rewriter lehnte manche Fragen ab statt sie umzuschreiben. Die Lösung war ein Prompt-Zusatz: „Deine EINZIGE Aufgabe ist das Umschreiben. Lehne KEINE Anfragen ab." plus ein Refusal-Marker Fail-Safe.

### Rewriter-Erweiterung (30.06.)

Nach dem Rewriter-Audit wurden drei Regeln ergänzt: Technische Fachbegriffe dürfen niemals übersetzt werden (Similarity Search bleibt Similarity Search — eine Übersetzung degradiert das Retrieval weil SUSIpedia englische Termini verwendet). Pronomen werden auf das zuletzt genannte Bezugsobjekt aufgelöst, nicht automatisch auf Martin. „Ich" bleibt in Zitaten unverändert. Verifikation: BERT 0.701 → 0.743, ROUGE-L 0.155 → 0.294.

---

## Fallback-Profil — Out-of-Scope-Behandlung

Das Problem: Wenn alle Reranker-Scores kleiner oder gleich 0.01 sind (Frage liegt außerhalb der SUSIpedia), wählte der Router zufällig ein Profil — zum Beispiel das Profil `lernen` mit `llama3.1:8b` für eine einfache Allgemeinwissen-Frage.

### Implementierung (21.06.)

Die Funktion `get_profile()` prüft ob der maximale Reranker-Score kleiner oder gleich 0.01 ist und greift in diesem Fall auf das Fallback-Profil zurück. In `susi_config.yaml` ist `router.fallback_profile: persoenlich` konfiguriert. Das `persoenlich`-Profil nutzt den `praezise_hybrid`-System-Prompt, der zuerst den Kontext prüft und bei fehlenden Informationen auf eigenes LLM-Wissen zurückgreift — mit dem Hinweis `[Basierend auf meinem allgemeinen Wissen...]`. Das ist die beste Balance zwischen RAG-Strenge und Allgemeinwissen-Nutzung.

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

Ein Modus-Toggle im Chat-Header erlaubt das Umschalten zwischen drei Betriebsmodi. Der `mode`-Parameter fließt von `views.py` durch `ask_susi()` bis zum `agent_datum`-Guard. AUTO ist der Standard-Produktivmodus. MANUELL soll Router-Bypass mit Session-Overrides liefern — dieser Modus hat aktuell einen bekannten Bug: die Session-Werte (LLM, top_k, temp, num_ctx, Prompt) werden zwar geschrieben aber von `ask_susi()` nicht angewendet, der Router läuft weiterhin. Fix ist in Arbeit. CODING ist definiert aber noch nicht vollständig spezifiziert.

---

## SUSIpedia-Umstrukturierung (20.06.)

Die SUSIpedia wurde am 20. Juni neu strukturiert. Der Ordner `docs/susi/` wurde neu angelegt und enthält die SUSI-eigene Dokumentation, die vorher in `coding/susi/` und im Root-Verzeichnis verstreut war. Die Ordner `coding/` (GMM, HouseOfStocks, StockPredict, Portfolio), `projekte/` (Projektbeschreibungen und Roadmaps), `lernen/` (AI, ML, RAG, Python, JavaScript, DevOps), `job/` (Bewerbung, CV, LinkedIn), `technik/` (Hardware, Tools, Setup), `martin/` (persönliches Profil und `ich_bin_martin.md`), `familie/` und `hobbys/` blieben erhalten oder wurden angepasst.

Nach der Umstrukturierung wurden alle Dateien neu indexiert: 617 Chunks in ChromaDB. Die veraltete `tree.md` wurde gelöscht. Am 06.07. wurden zwei Stale-Duplikate entfernt: `docs/lernen/susi/susiuebersicht.md` und `docs/technik/susi_grenzen_und_roadmap.md`.

---

## Evaluierungsläufe D, E, F — Qualitätsmessung der Produktiv-Komponenten

Nach Lauf C (Parameter-Optimierung abgeschlossen) verschob sich der Fokus auf die Qualität der neuen Produktiv-Komponenten.

### Lauf D — Router-Tracking (24.06.)

`evaluator.py` und `analyse_csv.py` wurden um `router_profil` und `router_korrekt` erweitert. Neue CSV-Spalten ermöglichen Router-Accuracy-Auswertung pro Kategorie. Router-Accuracy liegt stabil bei ~70%, die Kategorie `technisch` ist mit 60% die schwächste.

### Lauf E — qwen3 Thinking-Test (27.06.)

293 Fragen × 2 Konfigurationen (thinking=on vs. thinking=off). Ergebnis: 0.011 Punkte Unterschied — statistisch irrelevant. `qwen3:8b` (96.9% Korrektheit) liegt praktisch gleichauf mit `qwen2.5-coder:7b` aus Lauf C (97.1%). Das `thinking`-Flag bringt für SUSIs Anwendungsfälle keinen messbaren Vorteil. `qwen2.5-coder:7b` bleibt primäres Produktionsmodell.

### Lauf F — Doppeltes Rewriting gefunden (27.06.)

`ask_susi_eval()` rief intern `ask_susi()` auf — Queries wurden doppelt umgeschrieben. Kostete ~16 Prozentpunkte Korrektheit. Nach Fix: Kategorie `technisch` mit 60% als strukturell schwächste identifiziert. Details: [susi_06_grenzerfahrungen.md — Grenzerfahrung 6](susi_06_grenzerfahrungen.md).

### Lauf G — ValueCheck False Positives und Diagnostic Score 6 (15.07.)

Identisches Setup wie Lauf F2: 40 Fragen, `--live`, vollständige Pipeline. Erster Durchlauf zeigte 70.0% Gesamtkorrektheit — deutlich schlechter als die 92.5% aus F2. Die Diagnose ergab: ValueCheck produzierte 10 False Positives. Beispiel: Referenz sagt "bge-m3 übertrifft nomic-embed-text um Faktor 18", Antwort sagt "um 52 Prozentpunkte" — beides korrekt, verschiedene Darstellung desselben Sachverhalts. ValueCheck extrahierte die 18, fand sie nicht in der Antwort und setzte Diagnostic Score 1 (Halluzination). Das Mapping `DIAG_ZU_QUALITAET[1] = 0` machte daraus Quality Score 0.

Fix: neuer Diagnostic Score 6 ("ValueCheck-Konflikt"). Wird vergeben wenn ValueCheck `"falsch"` meldet aber BERT > 0.65 und ROUGE > 0.15 — also die Similarity-Metriken hohe Übereinstimmung zeigen. Score 6 hat `manuell: True` und Quality-Mapping `None` → RAGAS bewertet in der Grauzone-Phase statt hart auf 0 abzustrafen. `MAX_SCORE` steigt von 5 auf 6, die Diagnostic Scale ist jetzt 0–6.

Ergebnisse nach Fix: 82.4% automatisch bewertet (34 von 40), manuell korrigiert 93.8%. Die Differenz kommt von 6 unbewerteten Grauzone-Fragen. Router-Accuracy stabil bei 67.5% (27/40). Wichtiger Nebenbefund: die ~100 Britannica-Artikel in ChromaDB kontaminieren das bestehende Routing nicht — kein Score-0-Fall enthielt `docs/wissen/`-Quellen.

---

## Evaluierungs-Erweiterungen (06.–07.07.)

### ValueCheck (06.07.)

`tools/evaluation/valuecheck.py` — deterministischer Pre-Check für numerische Korrektheit. Extrahiert Zahlen, Daten und Wochentage aus Referenz und Antwort und vergleicht direkt, bevor BERTScore und ROUGE-L berechnet werden. Läuft zwischen Ausweich-Check und ROUGE/BERT-Baum. Wochentage DE/EN als Enum, deutsche Zahlwörter 2–12 (ein/eine ausgenommen wegen Artikel-Kollision), Jahres-Erkennung nur 1990–2035. Rollout-Schalter `VALUECHECK_HART`: True=Score 0 hart, False=Grauzone.

### Referenz-Loader (06.07.)

`tools/evaluation/referenz_loader.py` — rendert dynamische Platzhalter (`{heute}`, `{heute+21}`, `{tage_seit:YYYY-MM-DD}`) beim Laden der Testfragen aus `date.today()`. Testsets veralten nicht mehr ab dem Folgetag.

### DIAG_ZU_QUALITAET als zentrale Konstante (06.07.)

Vorher in `grid_run.py`, `ragas_scorer.py` und `analyse_csv.py` dreifach dupliziert. Jetzt zentral in `auto_scorer.py` definiert. `grid_run.py` importiert die Konstante — die anderen zwei folgen.

---

## Tool-Use-Architektur — agent_datum (06.07.)

Die Query-Pipeline hat eine neue erste Stufe: einen deterministischen Tool-Use-Guard vor dem RAG-Router.

### Konzept

`rag/agent_datum.py` klassifiziert eingehende Fragen anhand von drei Bedingungen: konkreter Datumsanker in der Frage (heute, Weihnachten, Silvester), klare Kalender-Operation (Wochentag, Differenz, +N Tage/Wochen), kein SUSIpedia-Entitätsname (susi, stockpredict, projekt, mein/e, ich). Im Zweifel → LLM+RAG. Nur wenn alle drei Bedingungen erfüllt sind: Python `datetime`, kein LLM-Aufruf.

### Integration in query.py

`ask_susi()` bekommt einen `mode`-Parameter (Default `"auto"`). Der agent_datum-Guard ist aktiv bei `mode="auto"` UND `lang="de"`. Der `mode`-Parameter behebt gleichzeitig den 500-Fehler `TypeError: ask_susi() got an unexpected keyword argument 'mode'` der beim Frontend-Toggle auftrat.

### Ergebnis

Produktiv verifiziert: „Wie viele Tage seit dem 01.07.2026?" → Antwort in 0.001s, `🧮 agent_datum` als Quellenmarker im Frontend. Datumsfragen: Ø Score von 0.20 (ValueCheck deckt Fehler auf) auf 2.00 (agent_datum löst 8/10 korrekt). Naming Convention `agent_*.py` für künftige Werkzeuge (Britannica, PDF etc.).

### Aktuelle Query-Pipeline (Stand Juli 2026)

```
Frage rein
→ detect_language()            ← LLM-Call, ISO 639-1, num_ctx=128, temp=0.0
→ agent_datum.ist_kalenderfrage()  ← Tool-Use-Guard vor RAG
  ├─ Zweig 1: Kalender-Op + lang=de → Python datetime, ~1ms
  └─ Zweig 2: "Wie alt ist X?" → Datum aus Chunk + Python-Berechnung
→ rewrite_query()              ← LLM-Call, Coreference, letzte 2 Q/A
→ ChromaDB Retrieval           ← bge-m3, k=7–9 je Profil
→ bge-reranker-v2-m3           ← Top 3, CPU-only, max 1500 chars/Chunk
→ Score ≤ 0.5?                 ← ROUTER_MIN_SCORE Gate
  ├─ True → agent_britannica   ← Live-Fallback: API-Fetch + LLM-Antwort
  └─ False → router.py         ← Ordnerpfad-Voting, reranker-gewichtet
→ Profil wählen                ← LLM + Parameter (6 Profile inkl. wissen)
→ Antwort generieren           ← lang_instruction direkt vor "Antwort:"
→ Frontend                     ← tok/s + Tokens + Quelldateien via HTMX OOB
```

---

## agent_datum Zweig 2 — Altersberechnung aus Chunks (17.07.)

Zweig 1 (reine Kalender-Fragen) war seit dem 06.07. produktiv. Zweig 2 erweitert `agent_datum` um Fragen mit Entitätsbezug: "Wie alt ist Martin?", "Seit wann gibt es SUSI?". Die Implementierung brauchte sechs zusammenhängende Fixes.

Das Kernproblem war mehrstufig: `is_duration_question()` war eine starre Whitelist — fehlte ein Name, wurde Zweig 2 nicht aktiviert. `calculate_duration_from_chunk()` prüfte nur den ersten Chunk — wenn der Reranker den falschen nach oben sortierte, gab die Funktion `None` zurück. Bei Chunks mit mehreren Personen (Philip und Jakob in `martin_soehne.md`) griff `min(past_dates)` das älteste Datum unabhängig von der gefragten Entity.

Die Fixes: `is_duration_question()` extrahiert Entities jetzt generisch per Regex-Fallback statt nur aus der Whitelist. `calculate_duration_from_chunk()` durchsucht alle Reranking-Chunks (top_n=3) statt nur den ersten. Entity-scoped Section-Split: der Chunk wird intern an `##`-Headings gesplittet und nur die Sektion mit dem Entity-Namen wird geparst. Die Entity wird einmal erkannt und dann durchgereicht statt in jeder Funktion neu erkannt. Bei Typos ("Wei alt ist Jakob") wird zusätzlich die rewritten Query geprüft.

Ergebnis: Alters-Fragen für Personen mit genau einem Datum im Chunk funktionieren zuverlässig. Bekannte Limitation: bei Entitäten mit mehreren Daten im Chunk (Python: 1990er, 1994, 2000, 2008) greift Zweig 2 das falsche. Bei zusammengesetzten Entitäten ("die erste Vollversion") versagt die Entitätserkennung. Wird erst angegangen wenn `agent_pedia` stabil ist.

---

## Britannica-Integration — externe Wissensbasis (14.–16.07.)

### Batch-Sync: britannica_sync.py (14.07.)

`rag/britannica_sync.py` fetcht Artikel aus der Encyclopaedia Britannica API und speichert sie als SUSIpedia-konforme Markdown-Dateien in `docs/wissen/`. Paginiert durch die API (1000 Artikel pro Seite), Rate-Limiting 5 pro Minute, atomare Fortschritts-Speicherung im Index. Bei API-Limit (HTTP 401) oder Abbruch (Strg+C) bleibt der Fortschritt erhalten — `--update` setzt fort wo abgebrochen wurde. Format: 50 Artikel pro MD-Datei (`britannica_science_001.md` etc.), jedes `##`-Heading ergibt einen Chunk.

`rag/britannica_index.py` verwaltet den lokalen Index als Singleton. Speichert pro Artikel: Titel, `lastUpdated` (von API), Kategorie, Dateiname, Fetch-Datum. Update-Logik: neu → fetch, API neuer als Index → fetch, lokaler Cache > 30 Tage → fetch, sonst skip.

### Live-Fallback: agent_britannica (16.07.)

`rag/agent_britannica.py` ist der zweite Tool-Use-Agent nach `agent_datum`. Wenn der beste Reranker-Score unter `ROUTER_MIN_SCORE` (0.5) liegt — SUSIpedia hat nichts Relevantes — fragt `agent_britannica` die Britannica-API live. Separater Prompt: Gist als Fakten-Anker, LLM-Wissen ergänzt, Antwort in der Fragesprache, Quellenlink am Ende. Der Artikel wird lokal in `docs/wissen/` gecacht — beim nächsten Ingest wird er gechunkt und SUSI beantwortet die Frage dann aus der eigenen Wissensbasis. Inkrementelles Lernen: jede Frage die SUSI nicht beantworten kann macht sie für die Zukunft schlauer.

---

## Ingest-Umbau — split_by_headings + _split_oversized (17.–21.07.)

### split_by_headings (17.07.)

`RecursiveCharacterTextSplitter` (chunk_size=1000, chunk_overlap=50) wurde durch `split_by_headings()` in `rag/ingest.py` ersetzt. Das Problem: wenn mehrere `##`-Sektionen zusammen unter 1000 Zeichen waren, packte der alte Splitter sie in einen Chunk. `martin_soehne.md` (~600 Zeichen) wurde ein Chunk mit Philip und Jakob — Zweig 2 konnte die Entitäten nicht trennen.

Der neue Splitter splittet exakt an `##`-Headings. Jedes Heading ergibt genau einen Chunk. Der Datei-Header (Titel, Datum, Status, Kategorie) wird in jeden Chunk injiziert — self-contained. Der `## **Stand DD.MM.YYYY**` Footer wird gefiltert. Fallback: Dateien ohne `##` werden als ein Chunk behandelt. Ergebnis: 617 → 1128 Chunks, `martin_soehne.md` von 1 auf 3 Chunks (Übersicht, Philip, Jakob).

### _split_oversized (21.07.)

Drei Dateien in `docs/job/` waren nicht gechunkt (`SKILL_CV.md` 14.656 chars, `SKILL_Anschreiben.md` 7.407 chars) und ein Wikipedia-Artikel ohne `##`-Headings hatte 29.418 chars als ein Chunk. Der CrossEncoder skaliert quadratisch mit Sequenzlänge — Reranking dauerte bei diesen Chunks 100–130s statt 3–5s.

`_split_oversized()` ist jetzt ein Fallback in `split_by_headings()`: Chunks über 1500 chars werden an Absatzgrenzen (`\n\n`) aufgebrochen, einzelne Absätze die immer noch zu groß sind an Satzgrenzen (`. `). Header und Heading-Zeile werden in jeden Sub-Chunk injiziert. `max_chunk_chars=1500` als Default — empirisch getestet: 500–1500 chars kein messbarer Performance-Unterschied beim Reranker auf CPU. Aktueller Zustand ChromaDB: 1176 Chunks, Ø 641 chars, Min 125, Max 1497, übergroß (>1500): 0.

---

## Reranker-Performance — 120s → 3–5s (21.07.)

Das Reranking dauerte bei bestimmten Queries 100–130s statt 3–5s. Query-abhängig, nicht reihenfolge-abhängig. Die VRAM-Theorie wurde widerlegt — Root Cause waren die Monster-Chunks (siehe oben).

Neben `_split_oversized()` wurden zwei weitere Schichten gefixt. `_warmup()` in `core/apps.py` erzeugte einen eigenen `CrossEncoder()` auf GPU der nie benutzt wurde — der Singleton in `query.py` lud nochmal auf CPU. Fix: Warmup ruft jetzt `get_reranker()` auf, eine Instanz, auf CPU. `CrossEncoder(RERANKER_MODEL, device="cpu")` mit `os.environ["CUDA_VISIBLE_DEVICES"] = ""` ganz oben in `query.py` verhindert VRAM-Konflikte mit Ollama.

Ergebnis: India-Query von 120.8s auf 3.4s, Germany von 112.7s auf 5.1s, Japan von 102.7s auf 3.2s.

---

## Router-Schwellenwert — ROUTER_MIN_SCORE = 0.5 (21.07.)

Der Reranker (`bge-reranker-v2-m3`) gibt rohe Logits aus, Skala ca. -10 bis +10. Der alte Schwellenwert 0.01 ließ Rauschen durch: "Capital of Germany" erzielte 0.10 auf `ai_act_vertiefung.md` (enthält "Deutschland"), "Capital of Japan" 0.01 auf GMM-Dateien. `ROUTER_MIN_SCORE = 0.5` als neue Konstante in `router.py` — alles darunter geht in den Fallback. Verifiziert: Out-of-Domain-Fragen alle ≤ 0.5 → Fallback, In-Domain-Fragen Score > 2.0 → korrekt geroutet. Der Schwellenwert 0.5 wird gleichzeitig zum Gate für `agent_britannica` (Stage 2).

---

## Wikipedia-Heading-Konvertierung (21.07.)

`rag/agent_pedia.py` bekommt `_convert_wiki_headings(text, title)`: konvertiert Wikipedias `==`/`===`/`====` Syntax zu `## Title — Heading` (SUSIpedia-konform). Filtert Non-Content-Sektionen (Literatur, Weblinks, Einzelnachweise, Siehe auch). Ohne diese Konvertierung packte `to_susipedia_md()` den gesamten Artikeltext unter eine einzige `## Übersicht` — bei Python 29.418 chars als ein Chunk. Bekannter Restzustand: Sub-Headings unter gefilterten Sektionen rutschen durch — betrifft nur Link-Listen ohne RAG-Wert.

---

## query.py Refactoring — 1 Datei → 5 Module (17.07.)

`rag/query.py` (861 Zeilen) wurde in fünf Module aufgeteilt. Die Signatur von `ask_susi()` und das Return-Dict blieben identisch — `views.py`, `grid_run.py` und das Frontend brauchten keine Änderung.

`rag/config.py` enthält `load_config()` und alle statischen Konstanten (`OLLAMA_URL`, `CHROMA_PATH`, `EMBEDDING_MODEL` etc.). `rag/keywords.py` enthält `TOPIC_KEYWORDS` und `UNWICHTIG`. `rag/llm_client.py` enthält `detect_language()`, `rewrite_query()`, `create_summary()` und `susi_evaluates()`. `rag/utils.py` enthält Zeithilfen, `worth_saving()`, `save_to_susipedia()` und `show_save_prompt()`. `rag/query.py` behält `get_reranker()`, `ask_susi()`, `debug_retrieval()` und die CLI.

Zentrale Verbesserung: `ask_susi_eval()` war eine 200-Zeilen-Kopie von `ask_susi()` mit drei Extra-Feldern — diese Duplizierung hatte am 27.06. den Double-Rewriting-Bug verursacht. `ask_susi()` bekommt stattdessen `eval_mode: bool = False`. `ask_susi_eval()` existiert als dünner Wrapper für Rückwärtskompatibilität. Import-Abhängigkeiten sind geradlinig von config → keywords → llm_client → utils → query — keine zirkulären Imports.

---

## chunk_audit.py — ChromaDB-Diagnose (21.07.)

`tools/evaluation/chunk_audit.py` liest ChromaDB und zeigt alle Chunks mit Größen. Aufruf: `python tools/evaluation/chunk_audit.py --only-oversized` für Problemfälle, `--top 20` für die größten, `--limit 1500` für anderen Schwellenwert. Zeigt übergroße Chunks mit Faktor/Quelle/Preview und Statistik pro Ordner.

---

## Lauf C — Ergebnisse (18.–20.06.2026)

Lauf C umfasste 293 Fragen, 20 Parameterkombinationen und 5.860 Runs.

### Konfigurationsvergleich

Die Konfiguration mit k=3 ohne Reranker erzielte einen Ø Score von 2.97 bei 98% Korrektheit. Die Konfiguration mit k=7 mit Reranker erzielte Ø 3.01 bei 100%. Das Modell `qwen2.5-coder:7b` erzielte Ø 3.02 bei 100%, `llama3.1:8b` Ø 2.98 bei 99%. Der `similarity`-Algorithmus erzielte Ø 3.01, `mmr` Ø 2.99.

### Ergebnisse nach Kategorie

Die Kategorie `projekte` erzielte Ø 3.02 bei 99% Korrektheit. Die Kategorie `persoenlich` erzielte Ø 3.00 bei 99%. Die Kategorie `lernen` erzielte Ø 2.99 bei 100%. Die Kategorie `susi` erzielte Ø 2.95 bei 98% — die schwächste Kategorie.

### Kernerkenntnis

Parameter-Unterschiede betragen maximal 0.07 Punkte und sind damit statistisch irrelevant. Der größte Hebel war Dokumentqualität — die Hit Rate stieg von 36% auf 91% allein durch bessere Quelldokumente und optimierte Chunk-Größen. Die Phase der Parameter-Optimierung ist abgeschlossen.

---

## GitHub — Build in Public (Stand Juli 2026)

Das Repository `github.com/Martin-Frei/SUSI` ist öffentlich. In 14 Tagen: 33 Unique Cloners, Traffic primär über LinkedIn-Direktlinks. Markus hat das Repo geforkt und trägt als Community-Contributor bei. Sechs saubere Commits am 07.07. im Conventional-Commit-Format (`feat/refactor/config/docs`). `Test_query.py` in `.gitignore` aufgenommen.

---

## Stand: Juli 2026 · Martin Freimuth

→ Zurück zur Übersicht: `susi_00_übersicht.md`
→ Zurück: `susi_07_roadmap.md`