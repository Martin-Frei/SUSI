# SUSI — Kapitel 08 — Vom evaluierten System zum produktiven Assistenten
Datum: 2026-07-08
Status: aktiv
Zeitraum: 12. Juni – 08. Juli 2026

---

## Kapitel 08 — Übergang in den Produktivbetrieb

Dieses Kapitel dokumentiert den Übergang von SUSI aus der Evaluierungsphase (Kapitel 00–07) in den aktiven Produktivbetrieb. Im Mittelpunkt stehen die zentrale Konfiguration via `susi_config.yaml`, die Reranker-Evolution, der retrieval-getriebene Router, Query Rewriting, Fallback-Profil, Chat-History in SQLite sowie die Tool-Use-Architektur mit `agent_datum`.

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

Das Profil `susi` gilt für den Ordner `docs/susi/` und nutzt `qwen2.5-coder:7b` mit top_k 7, top_n 3 und temperature 0.0. Das Profil `projekte` gilt für `docs/coding/` und `docs/projekte/` mit denselben Parametern. Das Profil `lernen` gilt für `docs/lernen/` und nutzt `llama3.1:8b` mit top_k 9, top_n 5 und temperature 0.3. Das Profil `persoenlich` gilt für `docs/martin/`, `docs/job/`, `docs/familie/` und `docs/hobbys/` mit `qwen2.5:7b`, top_k 5, top_n 3 und temperature 0.0. Das Profil `technik` gilt für `docs/technik/` mit `qwen2.5-coder:7b`, top_k 5, top_n 3 und temperature 0.0.

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

---

## Evaluierungs-Erweiterungen (06.–07.07.)

### ValueCheck (06.07.)

`tools/evaluation/valuecheck.py` — deterministischer Pre-Check für numerische Korrektheit. Extrahiert Zahlen, Daten und Wochentage aus Referenz und Antwort und vergleicht direkt, bevor BERTScore und ROUGE-L berechnet werden. Läuft zwischen Ausweich-Check und ROUGE/BERT-Baum. Wochentage DE/EN als Enum, deutsche Zahlwörter 2–12 (ein/eine ausgenommen wegen Artikel-Kollision), Jahres-Erkennung nur 1990–2035. Rollout-Schalter `VALUECHECK_HART`: True=Score 0 hart, False=Grauzone.

**Erweiterung (15.07.):** Neuer Diagnostic Score 6 (ValueCheck-Konflikt). Wird vergeben wenn ValueCheck `status="falsch"` meldet aber BERT > 0.65 UND ROUGE > 0.15 — die Antwort ist inhaltlich korrekt, verwendet aber andere Zahlendarstellungen als die Referenz. Score 6 mappt auf `None` (Grauzone für RAGAS). Entdeckt in Lauf G: 10 von 40 Fragen waren False Positives durch den alten harten Score-1-Pfad.

### Referenz-Loader (06.07.)

`tools/evaluation/referenz_loader.py` — rendert dynamische Platzhalter (`{heute}`, `{heute+21}`, `{tage_seit:YYYY-MM-DD}`) beim Laden der Testfragen aus `date.today()`. Testsets veralten nicht mehr ab dem Folgetag.

### DIAG_ZU_QUALITAET als zentrale Konstante (06.07.)

Vorher in `grid_run.py`, `ragas_scorer.py` und `analyse_csv.py` dreifach dupliziert. Jetzt zentral in `auto_scorer.py` definiert. `grid_run.py` importiert die Konstante — die anderen zwei folgen. Das Mapping: 0→0, 1→0, 2→1, 3→2, 4→0, 5→0, 6→None (ValueCheck-Konflikt, seit 15.07.).

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
  ├─ True + mode=auto|manuell + lang=de → Python datetime, ~1ms
  └─ False → normale Pipeline
→ rewrite_query()              ← LLM-Call, Coreference, letzte 2 Q/A
→ ChromaDB Retrieval           ← bge-m3, k=7–9 je Profil
→ bge-reranker-v2-m3           ← Top 3
→ router.py                    ← Ordnerpfad-Voting, reranker-gewichtet
→ Profil wählen                ← LLM + Parameter
→ Antwort generieren           ← lang_instruction direkt vor "Antwort:"
→ Frontend                     ← tok/s + Tokens + Quelldateien via HTMX OOB
```

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

## Lauf G — ValueCheck-Konflikt entdeckt *(15.07.2026)*

Identisches 40-Fragen-Setup wie Lauf F2. Erster Durchlauf zeigte 70.0% Gesamtkorrektheit — ein deutlicher Rückschritt gegenüber F2 (92.5%). Ursache: 10 von 12 Score-0-Einträgen waren False Positives durch ValueCheck. Die Antworten waren inhaltlich korrekt, verwendeten aber andere Zahlendarstellungen als die Referenz (z.B. „Faktor 18" vs. „52 Prozentpunkte" — beides korrekt, verschiedene Perspektive auf denselben Sachverhalt). ValueCheck setzte Diagnostic Score 1, `DIAG_ZU_QUALITAET[1] = 0` machte daraus Quality 0, RAGAS übersprang die Zeilen weil bereits ein `auto_score` existierte.

**Fix:** Neuer Diagnostic Score 6 (ValueCheck-Konflikt). Vergeben wenn ValueCheck `status="falsch"` meldet aber BERT > 0.65 UND ROUGE > 0.15. Score 6 hat `manuell: True` → `grid_run.py` setzt `score_man = None` → RAGAS bewertet in der Grauzone-Phase. Bei niedrigen Metriken bleibt Score 1 (harter Fehler). Änderungen in `auto_scorer.py`: `MAX_SCORE = 6`, `DIAG_ZU_QUALITAET` um `6: None`, ValueCheck-Block prüft `metriken_hoch` vor hartem Score 1.

**Ergebnisse nach Fix:** 82.4% Gesamtkorrektheit (34/40 bewertet, 6 in Grauzone). Bei konservativer Annahme (alle 6 Grauzone-Fragen korrekt) liegt die bereinigte Korrektheit bei ~92%. Router-Accuracy stabil bei 67.5% (27/40) — falsch geroutete Fragen bekamen trotzdem gute Scores, der Router ist nicht der Engpass. RAGAS löste 16 von 17 Grauzone-Fragen korrekt. Die ~100 Britannica-Artikel in ChromaDB kontaminierten das bestehende Routing nicht.

**Offene Punkte aus Lauf G:** Referenzantwort tech_03 veraltet (`chunk_size=300/500` statt produktiv `1000`). Frage proj_05 mehrdeutig (Portfolio vs. HouseOfStacks). `ragas_scorer.py` und `analyse_csv.py` müssen ihre lokalen `DIAG_ZU_QUALITAET`-Duplikate um Score 6 erweitern.

---

## GitHub — Build in Public (Stand Juli 2026)

Das Repository `github.com/Martin-Frei/SUSI` ist öffentlich. In 14 Tagen: 33 Unique Cloners, Traffic primär über LinkedIn-Direktlinks. Markus hat das Repo geforkt und trägt als Community-Contributor bei. Sechs saubere Commits am 07.07. im Conventional-Commit-Format (`feat/refactor/config/docs`). `Test_query.py` in `.gitignore` aufgenommen.

---

## Stand: Juli 2026 · Martin Freimuth

→ Zurück zur Übersicht: `susi_00_übersicht.md`
→ Zurück: `susi_07_roadmap.md`