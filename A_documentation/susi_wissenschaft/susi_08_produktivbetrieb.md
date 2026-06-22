# SUSI — Kapitel 08 — Vom evaluierten System zum produktiven Assistenten
Datum: 2026-06-22
Status: aktiv
Zeitraum: 12.–22. Juni 2026

---

## Kapitel 08 — Übergang in den Produktivbetrieb

Dieses Kapitel dokumentiert den Übergang von SUSI aus der Evaluierungsphase (Kapitel 00–07) in den aktiven Produktivbetrieb zwischen dem 12. und 22. Juni 2026. Im Mittelpunkt stehen die zentrale Konfiguration via `susi_config.yaml`, die Reranker-Evolution, der retrieval-getriebene Router, Query Rewriting, Fallback-Profil und Chat-History.

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

Der produktive Router funktioniert so: Die Frage geht in das Retrieval mit k=7, der Reranker sortiert die Top 3. Der Router analysiert die Herkunft der Chunks anhand der Ordnerpfade und führt ein reranker-gewichtetes Voting durch, bei dem Score multipliziert mit Kategorie berechnet wird. Das Profil mit dem höchsten Gewicht gewinnt und bestimmt LLM sowie alle Parameter für die Antwortgenerierung.

### Router-Profile (Stand 20.06.)

Das Profil `susi` gilt für den Ordner `docs/susi/` und nutzt `qwen2.5-coder:7b` mit top_k 7, top_n 3 und temperature 0.0. Das Profil `projekte` gilt für `docs/coding/` und `docs/projekte/` mit denselben Parametern. Das Profil `lernen` gilt für `docs/lernen/` und nutzt `llama3.1:8b` mit top_k 9, top_n 5 und temperature 0.3. Das Profil `persoenlich` gilt für `docs/martin/`, `docs/job/`, `docs/familie/` und `docs/hobbys/` mit qwen2.5-coder:7b, top_k 5, top_n 3 und temperature 0.0. Das Profil `technik` gilt für `docs/technik/` mit denselben Parametern wie persoenlich.

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

---

## Fallback-Profil — Out-of-Scope-Behandlung

Das Problem: Wenn alle Reranker-Scores kleiner oder gleich 0.01 sind (Frage liegt außerhalb der SUSIpedia), wählte der Router zufällig ein Profil — zum Beispiel das Profil `lernen` mit `llama3.1:8b` für eine einfache Allgemeinwissen-Frage.

### Implementierung (21.06.)

Die Funktion `get_profile()` prüft ob der maximale Reranker-Score kleiner oder gleich 0.01 ist und greift in diesem Fall auf das Fallback-Profil zurück. In `susi_config.yaml` ist `router.fallback_profile: persoenlich` konfiguriert. Das `persoenlich`-Profil nutzt den `praezise_hybrid`-System-Prompt, der zuerst den Kontext prüft und bei fehlenden Informationen auf eigenes LLM-Wissen zurückgreift — mit dem Hinweis `[Basierend auf meinem allgemeinen Wissen...]`. Das ist die beste Balance zwischen RAG-Strenge und Allgemeinwissen-Nutzung.

---

## Chat-History im Query Rewriter

Das Problem: Folgefragen verlieren ohne Kontext ihren Bezug und können nicht korrekt umgeschrieben werden.

### Implementierung (21.06.)

Die Funktion `rewrite_query()` bekommt einen `chat_history`-Parameter. Die letzten zwei Q/A-Paare aus der Django-Session werden übergeben, wobei Antworten auf 200 Zeichen gekürzt werden. Als Fail-safe gibt die Funktion bei jedem Fehler die Original-Frage zurück.

---

## Frontend-Entwicklung (12.–20.06.)

Das SUSI-Frontend wurde in dieser Phase um vier Komponenten erweitert.

### Einstellungs-Sidebar (12.06.)

Radio Buttons für LLM, Algorithmus und System-Prompt sowie Slider für top_k und temperature erlauben die direkte Konfiguration aus dem Frontend. Änderungen werden via HTMX sofort in der Config gespeichert.

### Retrieval-Info Sidebar (12.06.)

Nach jeder Frage wird live angezeigt: Anzahl gefundener Chunks, Anzahl nach Reranking und die Quelldateien. Der HTMX Out-of-Band Swap erfolgt ohne Extra-Request.

### tok/s-Anzeige (12.06.)

Unter jeder Antwort erscheinen Metriken wie `⚡ 84.2 tok/s · 97 Tokens · 5.42s · 🔁 reranked`. Diese Daten sind verfügbar durch den Wechsel auf die direkte Ollama REST API.

### SUSI-Icon und lokale Fonts (20.06.)

Das SUSI-Icon ist im Superman-Schild-Stil gestaltet: Gold (#9A7000) auf Dunkel (#12122a), großes S als Serif-Buchstabe, ViewBox eng gecroppt für Favicon-Nutzung. Google Fonts wurden durch lokale `@font-face`-Deklarationen ersetzt. JetBrains Mono in den Gewichten 300, 400 und 600 sowie Syne in 400, 700 und 800 werden lokal geladen — kein externer Request, vollständig DSGVO-konform.

---

## SUSIpedia-Umstrukturierung (20.06.)

Die SUSIpedia wurde am 20. Juni neu strukturiert. Der Ordner `docs/susi/` wurde neu angelegt und enthält die SUSI-eigene Dokumentation, die vorher in `coding/susi/` und im Root-Verzeichnis verstreut war. Die Ordner `coding/` (GMM, HouseOfStocks, StockPredict, Portfolio), `projekte/` (Projektbeschreibungen und Roadmaps), `lernen/` (AI, ML, RAG, Python, JavaScript, DevOps), `job/` (Bewerbung, CV, LinkedIn — `skills/` integriert), `technik/` (Hardware, Tools, Setup), `martin/` (persönliches Profil und `ich_bin_martin.md`), `familie/` und `hobbys/` blieben erhalten oder wurden angepasst.

Nach der Umstrukturierung wurden alle Dateien neu indexiert: 617 Chunks in ChromaDB. Die veraltete `tree.md` wurde gelöscht. Der SUSIpedia Converter Skill wurde mit der neuen Ordnerstruktur und den Router-Kategorien aktualisiert.

---

## Lauf C — Ergebnisse (18.–20.06.2026)

Lauf C umfasste 293 Fragen, 20 Parameterkombinationen und 5.860 Runs.

### Konfigurationsvergleich

Die Konfiguration mit k=3 ohne Reranker erzielte einen Ø Score von 2.97 bei 98% Korrektheit. Die Konfiguration mit k=7 mit Reranker erzielte Ø 3.01 bei 100%. Das Modell `qwen2.5-coder:7b` erzielte Ø 3.02 bei 100%, `llama3.1:8b` Ø 2.98 bei 99%. Der `similarity`-Algorithmus erzielte Ø 3.01, `mmr` Ø 2.99.

### Ergebnisse nach Kategorie

Die Kategorie `projekte` erzielte Ø 3.02 bei 99% Korrektheit. Die Kategorie `persoenlich` erzielte Ø 3.00 bei 99%. Die Kategorie `lernen` erzielte Ø 2.99 bei 100%. Die Kategorie `susi` erzielte Ø 2.95 bei 98% — die schwächste Kategorie mit bekanntem Retrieval-Problem durch fehlende Topic-Label Ankersätze in den SUSI-eigenen Dokumentationsdateien.

### Kernerkenntnis

Parameter-Unterschiede betragen maximal 0.07 Punkte und sind damit statistisch irrelevant. Der größte Hebel war Dokumentqualität — die Hit Rate stieg von 36% auf 91% allein durch bessere Quelldokumente und optimierte Chunk-Größen. Die Phase der Parameter-Optimierung ist damit abgeschlossen.

---

## Lauf D — Ausblick

Lauf D verschiebt den Fokus von Parameter-Optimierung auf Qualitätsmessung der neuen Produktiv-Komponenten.

### Was in Lauf D getestet wird

Die Router-Qualität wird anhand einer Validierung gegen manuelle Gold-Standard-Zuordnungen gemessen: Wählt der Router das richtige Profil? Der qwen3-Vergleich testet `qwen2.5-coder:7b` gegen `qwen3:14b` und `qwen3.5:9b` mit 30 bis 50 Fragen pro Kategorie. Der Thinking Mode untersucht die Auswirkung von `thinking on/off` auf die Antwortqualität, was ein qwen3-spezifisches Feature ist. Die `susi`-Kategorie erhält eine gezielte Miss-Analyse als schwächste Kategorie mit 98%.

### Umfang und neue Variablen

Lauf D ist kein Grid-Lauf, sondern umfasst 100 bis 150 gezielte Fragen mit 4 bis 6 Konfigurationen. Im Unterschied zu Lauf C ist der Router aktive Komponente, Query Rewriting ist aktiv, und qwen3 bringt den Thinking Mode als neue Variable.

---

## Stand: Juni 2026 · Martin Freimuth

→ Zurück zur Übersicht: `susi_00_übersicht.md`
→ Zurück: `susi_07_roadmap.md`