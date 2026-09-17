# 09 — Eval-Dashboard
### SUSI Entwicklungsbericht · Stand September 2026

---

## Ausgangslage

Bis Juni 2026 lief jede Evaluierung über die Kommandozeile. `grid_run.py` zog die Konfiguration aus `config.yaml`, schrieb eine CSV, und die Auswertung erfolgte in `analyse_csv.py` plus manuellem Review der Grauzonen im Terminal. Mit wachsender Grid-Größe entstanden drei konkrete Probleme.

**Kein Live-Feedback.** Ein Lauf mit 5.860 Runs dauerte Stunden. Fehlkonfigurationen — falsches Modell, leerer Fragensatz, abgestürzter Ollama-Server — fielen erst am Ende auf.

**Keine Persistenz.** Jeder Lauf war eine CSV-Datei ohne Datenbank. Vergleiche zwischen Läufen bedeuteten manuelles Joinen über Frage-IDs. Der Lauf-Name war ein Dateiname, kein Objekt mit Konfiguration, Status und Ergebnissen.

**Keine Interaktion.** Ergebnisse filtern, nach Kategorie sortieren, einzelne Fragen aufklappen, Antwort gegen Referenz stellen — all das war Terminal-Arbeit oder Excel-Handarbeit.

Das **SUSI Eval-Dashboard** ersetzt den bisherigen Grid-Runner: eine Django-App mit React-Frontend, die Evaluierungsläufe konfiguriert, live überwacht und interaktiv auswertet.

---

## Was das Dashboard anders macht

Der zentrale Unterschied zum Grid-Runner ist die **Trennung von Konfiguration, Ausführung und Auswertung in drei persistenten Schichten**:

```
QuestionSet — ein Fragenset als JSON in der Datenbank
↓
EvalRun — ein Lauf mit Konfiguration, Status, Fortschritt
↓
EvalResult — ein Einzelergebnis pro Frage × Kombination
```

Der Grid-Runner kannte nur die dritte Schicht — flache CSV-Zeilen. Das Dashboard kennt alle drei: Läufe sind reproduzierbar gespeichert, Fragensets wiederverwendbar, Ergebnisse abfragbar. Eine Frage kann gegen zwei Modelle verglichen werden ohne neue Messung.

Die zweite strukturelle Neuerung sind **Pipeline-Toggles als Grid-Achse**. Der Grid-Runner testete Parameter — `top_k`, `temperature`, `chunk_size`, Prompt-Varianten. Das Dashboard testet zusätzlich die Architektur-Komponenten selbst: Reranker an/aus, Rewriter an/aus, Router an/aus, `agent_datum` an/aus, `agent_pedia` an/aus. Jede Komponente kann isoliert bewertet werden. Diese Frage war mit dem Grid-Runner nicht systematisch beantwortbar.

---

## Backend — Django-App `eval`

Die Backend-App liegt im Ordner `eval/` und wird nicht öffentlich auf GitHub gepusht — nur das Frontend ist Teil des öffentlichen Repositories (vgl. Whitelist-Strategie in Kapitel 03).

### Die Datenmodelle

Drei Django-Models bilden den gesamten Zustand ab.

**`QuestionSet`** speichert ein Fragenset als JSON-String in der Datenbank. Das `set_type`-Feld unterscheidet drei Typen automatisch beim Speichern: `independent` (Typ 1 — unabhängige Fragen), `conversational` (Typ 2 — Fragen mit `kontext`-Feld für simulierte Chat-History) und `mixed`. Die Feld-Erkennung läuft in der `save()`-Methode: existieren sowohl Fragen mit als auch ohne `kontext`-Feld, wird das Set als `mixed` markiert. Die Anzahl der Fragen wird beim Speichern mitgeschrieben.

**`EvalRun`** speichert einen kompletten Lauf. Die Konfiguration liegt in drei JSON-Textfeldern: `models_config` (Array der zu testenden Modelle), `params_config` (Dict Parameter → Werteliste) und `pipeline_config` (Dict Pipeline-Toggle → `[true]`/`[false]`/`[true, false]`). Beim Erstellen berechnet `serializers.py` die Grid-Größe: `total_combinations = len(models) × (Π Parameter-Werte) × (Π Pipeline-Werte)` und `total_runs = total_combinations × question_count`. Ein optionaler `estimated_duration_sec`-Wert wird mit 12 Sekunden pro Frage veranschlagt.

Der Status-Zyklus ist explizit modelliert: `pending → running → completed | failed | aborted`. Das `abort_requested`-Boolean erlaubt kooperativen Abbruch — der Worker prüft es nach jeder Frage. Am Ende eines Laufs berechnet der Worker fünf Kennzahlen und schreibt sie direkt auf das Run-Objekt: `accuracy`, `avg_score`, `avg_bert`, `avg_rouge`, `avg_response_time`.

**`EvalResult`** speichert ein Einzelergebnis. Pro Zeile: Modellname, Fragetext, Kategorie, Referenzantwort, optional `chat_context` (JSON der simulierten History bei Typ-2-Fragen), `params_json` und `pipeline_json` der konkreten Kombination, die Antwort, die umgeschriebene Query, das Router-Profil, die Quelldateien als JSON, sowie alle Metriken aus `ask_susi()`: `tok_per_sec`, `response_time_sec`, `tokens_generated`, `chunks_found`, `chunks_after_reranking`. Dazu die drei Scoring-Werte: `auto_score` (Diagnostic Scale 0–6), `bert_score`, `rouge_l` und `quality_score` (Quality Scale 0–2, gemappt aus Diagnostic).

Die Trennung von `auto_score` und `quality_score` in der Datenbank ist eine Konsequenz aus Grenzerfahrung 1 (Kapitel 06): die undokumentierte Score-Skala war eine der ersten dokumentierten Fehlerquellen. Beide Skalen sind jetzt als explizite Felder vorhanden.

### Der Worker — `worker.py`

Der Worker läuft als **Django-Q-Background-Task**, gestartet von `views.py` über `async_task("eval.worker.execute_run", run.id)`. Der HTTP-Request kehrt sofort zurück, der Lauf läuft im Hintergrund weiter. Das Frontend pollt parallel den Status.

Die Iterationsreihenfolge:

```
Model (äußerste, einmal laden) → Params → Pipeline → Frage (innerste)
```

Das Modell wird pro Modellwechsel einmal vorgeladen über Ollamas `keep_alive`-Mechanismus. Ein leerer `/api/generate`-Call reicht — Ollama lädt das Modell in den VRAM und hält es für 300 Sekunden. Ein Modellwechsel dauert auf der RTX 3090 zwischen 5 und 15 Sekunden. Die äußere Schleife über Modelle minimiert die Anzahl der Wechsel.

Pro Frage durchläuft der Worker fünf Schritte: `ask_susi()` aufrufen (mit `eval_mode=True`), BERT und ROUGE berechnen, den Auto-Score vergeben, ein `EvalResult` in die Datenbank schreiben, den Fortschritt auf dem `EvalRun` aktualisieren. Danach prüft er `abort_requested` — ist es gesetzt, bricht er sauber ab und berechnet die Kennzahlen auf dem bis dahin erreichten Stand.

Die Scoring-Module werden dynamisch importiert — `evaluator.py`, `auto_scorer.py`, `referenz_loader.py` aus `tools/evaluation/`. Schlägt der Import fehl, läuft der Lauf ohne Scoring weiter statt abzubrechen. Die Pipeline bleibt damit unabhängig von der Scoring-Infrastruktur testbar.

Die Referenzen werden vor dem Lauf gerendert — dynamische Platzhalter (`{heute}`, `{heute+21}`, `{tage_seit:2026-07-01}`) werden über `referenz_loader.rendere()` aus `date.today()` aufgelöst. Das ist dieselbe Funktion, die in Kapitel 04 als zweite Schicht des Datumsarithmetik-Sprints eingeführt wurde.

Der Worker nutzt einen eigenen Logger `logs/eval_worker.log` mit rotierender Datei (2 MB, 3 Backups), getrennt vom Pipeline-Logger. `ask_susi()` loggt selbst über `rag/debug.py`; der Worker-Logger loggt nur die Orchestrierung — Lauf gestartet, Modell geladen, Kombination X/Y, Frage N/M, Abbruch, Fehler.

### Das Command `import_questions`

`python manage.py import_questions <json>` importiert bestehende Fragenset-JSONs in die Datenbank. Es erkennt drei Formate automatisch: flaches Array (`[{frage, referenz, kategorie}, ...]`), das alte `testfragen.json`-Format mit `smoke_test.fragen` und `full_evaluation.kategorien.*.fragen`, und das `testfragen_big_run.json`-Format mit `full_run.fragen`. Als Fallback durchsucht es alle Top-Level-Keys nach `fragen`-Arrays.

Die Normalisierung von `referenzantwort` → `referenz` und `quelle` → `quelldatei` passiert beim Import. Das Dashboard-Format ist einheitlich, die Quelldateien dürfen historisch gewachsen sein.

### Die API

Alle Endpunkte leben unter `/api/eval/`:

```
GET  /questionsets/              — alle Fragensets
POST /questionsets/              — neues Fragenset hochladen
GET  /questionsets/<id>/         — ein Fragenset mit allen Fragen
DELETE /questionsets/<id>/       — löschen (nur wenn kein Lauf es referenziert)

GET  /runs/                      — alle Läufe
POST /runs/                      — neuen Lauf erstellen + starten
GET  /runs/<id>/status/          — Polling: Status + Fortschritt + letzte 10 Ergebnisse
GET  /runs/<id>/results/         — Ergebnisse mit Filtern
POST /runs/<id>/abort/           — Lauf abbrechen
DELETE /runs/<id>/               — Lauf löschen (nur wenn nicht laufend)

GET  /models/                    — verfügbare Ollama-Modelle
```

Der `status`-Endpunkt liefert zusätzlich zu Status und Fortschritt die letzten zehn `EvalResult`-Zeilen. Das Frontend akkumuliert sie und hat damit ohne zusätzlichen Request Live-Feed und Chart-Daten.

Der `results`-Endpunkt akzeptiert vier Query-Parameter: `model`, `category`, `min_score`, `max_score`. Die Filterung passiert in der Datenbank. Zusätzlich liefert der Endpunkt aggregierte Statistiken (`avg_score`, `avg_bert`, `avg_rouge`, `avg_time`, `total`) über `django.db.models.Aggregate`.

Der `models`-Endpunkt fragt Ollamas `/api/tags` ab und gibt Modellname, Größe in GB und Änderungsdatum zurück. Die Filterung der Embedding-Modelle übernimmt das Frontend.

---

## Frontend — React-App `susi_frontend`

React 19 mit **Vite** als Build-Tool und **Tailwind CSS v4** über `@tailwindcss/vite`. Kein TypeScript — reines JSX. Die App läuft als separater Dev-Server gegen die Django-API auf `127.0.0.1:8008`. Die API-Base-URL kommt aus einer `.env`-Variable (`VITE_API_URL`). Das Frontend ist Teil des öffentlichen Repositories.

### Der State-Machine-Ansatz in `App.jsx`

Die App ist als explizite State-Machine gebaut mit vier Modi:

```
parameter → live → result → compare
```

`ParameterMode` ist die Landing-Page — hier wird konfiguriert und ein Lauf gestartet. `LiveMode` zeigt einen laufenden Lauf. `ResultMode` wertet einen abgeschlossenen Lauf aus. `CompareMode` vergleicht bis zu drei Läufe nebeneinander.

Die Top-Nav zeigt die vier Modi als Tabs. Nicht erreichbare Modi sind disabled — `Live` und `Results` ohne `activeRunId`, `Compare` ohne erste Run-Auswahl. Ein pulsierender grüner Punkt neben der Run-Nummer signalisiert einen aktiven Live-Lauf. Der Zustandsübergang `Parameter → Live` passiert durch `onStartRun(runId)`, der Übergang `Live → Result` durch `onCompleted(runId)` wenn der Lauf fertig ist.

### Der API-Layer in `services/api.js`

Alle HTTP-Aufrufe laufen durch eine zentrale `apiRequest()`-Funktion. Sie übernimmt JSON-Serialisierung, Fehler-Extraktion aus dem Response-Body und `204 No Content`-Handling. Der API-Layer exportiert elf Endpoint-Funktionen für Fragensets, Läufe, Polling und Modell-Liste. Dazu vier Utility-Funktionen:

**`pollRunStatus(runId, onUpdate, intervalMs)`** — ein generischer Polling-Helper der alle drei Sekunden `getRunStatus()` aufruft und bei `completed`/`failed`/`aborted` automatisch stoppt. Gibt eine `stop()`-Funktion zurück für manuelles Cleanup. Der Live-Modus muss keinen eigenen Timer verwalten.

**`generateRunName(questionSetName, models, params, pipeline)`** — generiert einen Lauf-Namen aus Datum, Fragenset-Name, Modell-Kurznamen und nur den Nicht-Default-Parametern. Beispiel: `2026-09-14_Datumsarithmetik_qwen2.5-coder_k5-9_t0.3`. Was in der Läufe-Übersicht steht, verrät die Konfiguration ohne Detail-Klick.

**`calculateGrid(models, params, pipeline, questionCount)`** — berechnet live die Grid-Größe, clientseitig. Der Server berechnet sie beim Erstellen ebenfalls; die doppelte Berechnung ist bewusst: der Client zeigt während der Konfiguration, der Server validiert beim Start.

**`formatDuration(seconds)`** — formatiert Sekunden in lesbare deutsche Strings (`~12 Minuten`, `~1,5 Stunden`).

### Die vier Seiten

**`ParameterMode`** ist die Landing-Page. Links die `ConfigSidebar` mit sieben Sektionen, rechts Platz für künftige Läufe-Übersicht (aktuell Empty-State). Beim Mount werden Modelle, Fragensets und vergangene Läufe geladen. Der komplette Config-State lebt hier: `selectedModels`, `params`, `pipeline`, `selectedQuestionSetId`, `runName`. Die `ConfigSidebar` ist ein reiner Layout-Wrapper, alle Werte fließen als Props runter und per Callback wieder hoch.

**`LiveMode`** pollt den Status-Endpunkt alle drei Sekunden. Es akkumuliert die neuen Ergebnisse aus jedem Poll in `allResults`, dedupliziert über `seenIndexesRef` (ein `Set` der bereits gesehenen Frage-Indizes) und verteilt an Charts und Terminal. Das Layout ist zweigeteilt: Charts links (50%), Terminal rechts (50%), Header oben volle Breite. Die kollabierbare `LiveParameterSidebar` überlagert bei Bedarf die Charts als absolut positionierte Schicht. Bei `completed` ruft es `onCompleted(runId)` auf — der Übergang zu `ResultMode` passiert automatisch nach 1,5 Sekunden Verzögerung. Bei `failed` zeigt es ein Fehlerbanner, bei `aborted` einen Hinweis mit Zähler („Run aborted — 423/5860 results available") und `New run`-Button. Die Partial-Ergebnisse bleiben sichtbar.

**`ResultMode`** lädt alle Ergebnisse eines Laufs und wendet Filter und Sortierung clientseitig an. Die Charts werden mit dem gefilterten Datensatz gespeist — dieselbe `LiveCharts`-Komponente wie im Live-Modus. Die Filter-Quick-Bar bietet Score-Presets (`Low ≤1`, `Mid 2`, `High 3`), Kategorie-Dropdown, Modell-Dropdown (nur bei Multi-Modell-Läufen) und sieben Sortier-Optionen inklusive tok/s. Der CSV-Export schreibt die aktuell gefilterte Ansicht. Das `ResultDetailModal` öffnet sich als Slide-Over von rechts und zeigt alle Metriken, Antwort gegen Referenz, Pipeline-Info und Quellen auf einen Blick.

**`CompareMode`** vergleicht bis zu drei Läufe. Die zentrale Design-Entscheidung ist die **Parameter-Intersection**: nur Werte, die in allen ausgewählten Läufen vorkommen, sind als Filter wählbar. Werte die nur in einem Lauf existieren sind disabled und durchgestrichen mit Tooltip „Missing in: …". Run A wählt aus allen Läufen, Run B und C filtern automatisch auf dasselbe Fragenset. Die Ergebnisse werden zeilenweise pro Frage gejoint und als Delta-Spalte gegen den Baseline-Lauf gezeigt. Regressions- und Improvements-Filter heben nur die Fragen hervor, bei denen sich die Scores unterscheiden. Expandierte Zeilen zeigen alle Antworten nebeneinander mit BERT, ROUGE, Time und tok/s.

### Die Komponenten

14 Komponenten in drei funktionalen Blöcken:

**Konfiguration** — `ConfigSidebar` assembliert sieben Sektionen. `QuestionSetPicker` (Dropdown + Vorschau-Button), `QuestionPreviewModal` (read-only Liste aller Fragen mit Kategorie-Badge und Referenzantwort, schließbar per X, Backdrop oder Escape), `ModelSelector` (Checkboxen mit Größenangabe in GB), `ParamChips` (Chip-Gruppen für `top_k`, `temperature`, `num_ctx`, `system_prompt`, `thinking` — mit `[+]`-Button für Custom-Werte), `PipelineToggles` (3-Wege-Segmented-Control On/Off/Both pro Komponente, farbcodiert grün/grau/orange), `GridPreview` (Live-Anzeige der Grid-Größe und geschätzten Dauer mit Farbschwellen grün/orange/rot).

**Live-Ansicht** — `LiveHeaderBar` (Progress-Bar, fünf KPI-Karten: Remaining, Avg/Question, Min, Max, tok/s, Abort-Button), `LiveCharts` (Boxplots pro Parameter + Kategorie-Boxplot + Response-Time-Scatter), `LiveTerminal` (scrollender Log-Feed mit Score-Farbkodierung, Auto-Scroll-Toggle mit automatischer Pause bei manuellem Scroll, Suchfeld, Status-Zeile mit aktuellem Modell und ETA), `LiveParameterSidebar` (kollabierbare Read-Only-Anzeige der laufenden Konfiguration mit Hervorhebung von Nicht-Default-Werten).

**Auswertung** — `ResultFilterBar` (Filter, Sort, Export, Compare, Delete), `ResultTable` (sortierbare Tabelle, Zeilen expandierbar mit Antwort vs. Referenz, Router-Profil, Sources), `ResultDetailModal` (Slide-Over mit allen Metriken in fünf Karten, Antwort vs. Referenz nebeneinander, Pipeline-Info als Grid, Quellen mit Agent-Marker; Chunk-Text als V2 markiert).

### LiveCharts — die aufwendigste Komponente

`LiveCharts` rendert drei Chart-Typen auf **Canvas** — kein Chart-Framework für die Boxplots, handgezeichnet mit `getContext("2d")`.

**Parameter-Boxplots** — pro Parameter mit mehr als einem Wert in der Grid-Konfiguration wird ein vertikaler Boxplot gerendert. Die Statistiken (Q1, Median, Q3, IQR, Whisker, Outliers) werden in `calcBoxStats()` nach Tukey berechnet: Whiskers bei Q1 − 1.5 × IQR und Q3 + 1.5 × IQR, Datenpunkte jenseits davon als Outlier-Dots. Jeder Chart hat drei Tabs: `auto_score`, `BERT`, `ROUGE-L`. Die Boxen zeigen die gefüllte Fläche Q1–Q3 mit weißem Median-Strich, Whisker-Caps und individuellen Outlier-Punkten.

**Kategorie-Boxplot** — ein horizontaler Boxplot, eine Zeile pro Kategorie. Die Kategorien sind dynamisch: sie erscheinen erst wenn ein Ergebnis mit dieser Kategorie in `results` auftaucht. Jede Kategorie hat eine eigene Farbe aus `CATEGORY_COLORS`. Die Höhe passt sich an die Anzahl der Kategorien an.

**Response-Time-Scatter** — X-Achse ist der Frage-Index, Y-Achse die Antwortzeit in Sekunden. Dots sind nach Modell eingefärbt mit Legende. Hover-Tooltip zeigt Frage, Score, BERT, Zeit, Modell, Router-Profil, Kategorie. Die Tooltip-Positionierung ist handgeschrieben — `canvas._dots` speichert die gezeichneten Kreise, der Hover-Handler findet den nächsten und positioniert das Tooltip-Div.

Canvas statt SVG oder Framework: die Charts müssen während eines Live-Laufs alle drei Sekunden mitwachsen ohne die Seite ruckeln zu lassen. Ein SVG-Baum mit 5.000 Dots ist teuer zu aktualisieren; ein Canvas wird neu gezeichnet.

### Design

Dunkles Terminal-Theme — `#12122a` Hintergrund, `#1a1a2e` Surface, Gold-Akzent `#9A7000`. Der Gold-Ton ist derselbe wie das SUSI-Icon im Hauptprojekt (Kapitel 08b). Die Terminal-Palette (grün/orange/rot/grau) wird konsistent für Score-Farbkodierung genutzt: Score ≥3 grün, Score 2 orange, Score ≤1 rot, Score 6 (ValueCheck-Konflikt) gelb mit Label „VC".

Die Farbpalette ist in `index.css` als Tailwind-v4-`@theme`-Block definiert — jede Farbe ist als Utility-Klasse nutzbar. Kein externer Font, keine externen Ressourcen. Das Dashboard lädt nichts von außen.

---

## Status

Das Dashboard ist seit September 2026 implementiert, aber noch nicht vollständig durchgetestet. Der erste vollständige Lauf über das Dashboard steht aus. Die folgenden Punkte sind daher Design-Aussagen, keine Messergebnisse.

**Möglich geworden:**
- Läufe sind persistent und reproduzierbar abfragbar (Django-ORM statt CSV-Parsing).
- Pipeline-Komponenten sind isoliert testbar (Reranker an/aus, Rewriter an/aus — als Grid-Achse).
- Fragensets sind wiederverwendbar (ein Upload, viele Läufe).
- Live-Feedback während des Laufs (Charts und Terminal aktualisieren sich alle drei Sekunden).
- Konversationsketten sind testbar (`kontext`-Feld → simulierte Chat-History).
- Läufe sind direkt vergleichbar (`CompareMode` mit Parameter-Intersection und Delta-Spalten).
- tok/s als KPI durchgehend sichtbar (Header, Terminal, ResultTable, CompareMode).

**Bewusst zurückgestellt:**
- Chunk-Text und Reranker-Scores im `ResultDetailModal` sind als V2 markiert. Die Chunks sind in `sources` als Datei-Pfade vorhanden, aber nicht als Text mit Scores.
- `tests.py` ist noch leer — das Dashboard hat noch keine automatisierten Tests.
- Die rechte Seite in `ParameterMode` ist aktuell Empty-State.
- Radar-Chart im CompareMode und klickbare Legenden im Scatter-Plot sind für V2 vorgesehen.

**Offene Design-Frage:** Die Grid-Schätzung mit 12 Sekunden pro Frage ist ein statischer Wert. Ob sie über verschiedene Fragensätze und Pipeline-Konfigurationen hinweg trägt, wird der erste echte Lauf zeigen. Der Live-Modus rechnet parallel mit `avg_response_time` aus den tatsächlich gemessenen Antworten und zeigt eine dynamische Restzeit-Schätzung — die statische Vorab-Schätzung in `ParameterMode` ist ungenauer als sie sein müsste.

---

→ *Zurück zur Übersicht: [susi_00_übersicht.md](susi_00_übersicht.md)*
→ *Vorheriges Kapitel: [susi_08_produktivbetrieb_evaluation.md](susi_08_produktivbetrieb_evaluation.md)*
*Stand: September 2026 · Martin Freimuth*