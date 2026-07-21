# SUSI — Kapitel 08a — Pipeline-Kernkomponenten
Datum: 2026-07-21
Status: aktiv
Zeitraum: 12. Juni – 21. Juli 2026

---

## Kapitel 08a — Was macht SUSI mit einer Frage?

Dieses Kapitel beschreibt die Kernkomponenten der SUSI-Query-Pipeline: Reranker, Modellauswahl, Router, Query Rewriting, Fallback-Behandlung und die Tool-Use-Agenten `agent_datum` und `agent_britannica`. Jede Komponente wird in der Reihenfolge vorgestellt in der sie historisch entstanden ist — nicht in der Reihenfolge in der sie in der Pipeline steht.

→ *Infrastruktur und Tooling: [susi_08_produktivbetrieb_infrastruktur.md](susi_08_produktivbetrieb_infrastruktur.md)*
→ *Evaluierung und Optimierung: [susi_08_produktivbetrieb_evaluation.md](susi_08_produktivbetrieb_evaluation.md)*

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

Sechs Profile steuern die Parameter pro Kategorie:

`susi` → `docs/susi/` → qwen2.5-coder:7b, top_k 7, top_n 3, temp 0.0
`projekte` → `docs/coding/`, `docs/projekte/` → gleiche Parameter wie susi
`lernen` → `docs/lernen/` → llama3.1:8b, top_k 9, top_n 5, temp 0.3
`persoenlich` → `docs/martin/`, `docs/job/`, `docs/familie/`, `docs/hobbys/` → qwen2.5:7b, top_k 5, top_n 3, temp 0.0
`technik` → `docs/technik/` → qwen2.5-coder:7b, top_k 5, top_n 3, temp 0.0
`wissen` → `docs/wissen/` (Britannica + Wikipedia, seit 17.07.) → llama3.1:8b, top_k 7, top_n 3, temp 0.1

### Warum Retrieval-getrieben besser ist als Frage-basiert

Der retrieval-getriebene Ansatz hat vier Vorteile. Er orientiert sich an der tatsächlichen Wissensbasis statt an Sprachmustern — das macht ihn robuster. Er ist selbst-konsistent: SUSI kennt ihre eigene SUSIpedia-Struktur. Er vermeidet Overfitting: neue Ordner werden automatisch einem Profil zugeordnet. Er benötigt keinen Extra-LLM-Call — die Reranker-Scores sind bereits vorhanden.

Das `thinking`-Flag ist in der Config und in `apply_profile()` für qwen3 vorbereitet. Bei einem Modellwechsel zu qwen3 genügt ein Eintrag in der Config — kein Code-Umbau nötig.

### Router-Schwellenwert — ROUTER_MIN_SCORE = 0.5 (21.07.)

Der Reranker (`bge-reranker-v2-m3`) gibt rohe Logits aus, Skala ca. -10 bis +10. Der alte Schwellenwert 0.01 ließ Rauschen durch: "Capital of Germany" erzielte 0.10 auf `ai_act_vertiefung.md` (enthält "Deutschland"), "Capital of Japan" 0.01 auf GMM-Dateien. `ROUTER_MIN_SCORE = 0.5` als neue Konstante in `router.py` — alles darunter geht in den Fallback. Verifiziert: Out-of-Domain-Fragen alle ≤ 0.5 → Fallback, In-Domain-Fragen Score > 2.0 → korrekt geroutet. Der Schwellenwert 0.5 wird gleichzeitig zum Gate für `agent_britannica` (Stage 2).

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

## Tool-Use-Architektur — agent_datum (06.07.)

Die Query-Pipeline hat eine neue erste Stufe: einen deterministischen Tool-Use-Guard vor dem RAG-Router.

### Konzept

`rag/agent_datum.py` klassifiziert eingehende Fragen anhand von drei Bedingungen: konkreter Datumsanker in der Frage (heute, Weihnachten, Silvester), klare Kalender-Operation (Wochentag, Differenz, +N Tage/Wochen), kein SUSIpedia-Entitätsname (susi, stockpredict, projekt, mein/e, ich). Im Zweifel → LLM+RAG. Nur wenn alle drei Bedingungen erfüllt sind: Python `datetime`, kein LLM-Aufruf.

### Integration in query.py

`ask_susi()` bekommt einen `mode`-Parameter (Default `"auto"`). Der agent_datum-Guard ist aktiv bei `mode="auto"` UND `lang="de"`. Der `mode`-Parameter behebt gleichzeitig den 500-Fehler `TypeError: ask_susi() got an unexpected keyword argument 'mode'` der beim Frontend-Toggle auftrat.

### Ergebnis

Produktiv verifiziert: „Wie viele Tage seit dem 01.07.2026?" → Antwort in 0.001s, `🧮 agent_datum` als Quellenmarker im Frontend. Datumsfragen: Ø Score von 0.20 (ValueCheck deckt Fehler auf) auf 2.00 (agent_datum löst 8/10 korrekt). Naming Convention `agent_*.py` für künftige Werkzeuge (Britannica, PDF etc.).

### agent_datum Zweig 2 — Altersberechnung aus Chunks (17.07.)

Zweig 1 (reine Kalender-Fragen) war seit dem 06.07. produktiv. Zweig 2 erweitert `agent_datum` um Fragen mit Entitätsbezug: "Wie alt ist Martin?", "Seit wann gibt es SUSI?". Die Implementierung brauchte sechs zusammenhängende Fixes.

Drei Probleme traten auf. Erstens: `is_duration_question()` war eine starre Whitelist — fehlte ein Name, wurde Zweig 2 nicht aktiviert. Zweitens: `calculate_duration_from_chunk()` prüfte nur den ersten Chunk — sortierte der Reranker den falschen nach oben, gab die Funktion `None` zurück. Drittens: bei Chunks mit mehreren Personen (Philip und Jakob in `martin_soehne.md`) griff `min(past_dates)` das älteste Datum unabhängig von der gefragten Entity.

Die Fixes: `is_duration_question()` extrahiert Entities jetzt generisch per Regex-Fallback statt nur aus der Whitelist. `calculate_duration_from_chunk()` durchsucht alle Reranking-Chunks (top_n=3) statt nur den ersten. Entity-scoped Section-Split: der Chunk wird intern an `##`-Headings gesplittet und nur die Sektion mit dem Entity-Namen wird geparst. Die Entity wird einmal erkannt und durchgereicht statt in jeder Funktion neu erkannt. Bei Typos ("Wei alt ist Jakob") wird zusätzlich die rewritten Query geprüft.

Ergebnis: Alters-Fragen für Personen mit genau einem Datum im Chunk funktionieren zuverlässig. Bekannte Limitation: bei Entitäten mit mehreren Daten im Chunk (Python: 1990er, 1994, 2000, 2008) greift Zweig 2 das falsche. Bei zusammengesetzten Entitäten ("die erste Vollversion") versagt die Entitätserkennung. Ein möglicher Ansatz wäre eine Heuristik die das Datum auswählt, das mit Begriffen wie "entwickelt", "erschienen" oder "veröffentlicht" im Chunk assoziiert ist — ähnlich der Entity-scoped Section-Split-Logik. Wird erst angegangen wenn `agent_pedia` stabil ist.

---

## Britannica-Integration — externe Wissensbasis (14.–16.07.)

### Batch-Sync: britannica_sync.py (14.07.)

`rag/britannica_sync.py` fetcht Artikel aus der Encyclopaedia Britannica API und speichert sie als SUSIpedia-konforme Markdown-Dateien in `docs/wissen/`. Paginiert durch die API (1000 Artikel pro Seite), Rate-Limiting 5 pro Minute, atomare Fortschritts-Speicherung im Index. Bei API-Limit (HTTP 401) oder Abbruch (Strg+C) bleibt der Fortschritt erhalten — `--update` setzt fort wo abgebrochen wurde. Format: 50 Artikel pro MD-Datei (`britannica_science_001.md` etc.), jedes `##`-Heading ergibt einen Chunk.

`rag/britannica_index.py` verwaltet den lokalen Index als Singleton. Speichert pro Artikel: Titel, `lastUpdated` (von API), Kategorie, Dateiname, Fetch-Datum. Update-Logik: neu → fetch, API neuer als Index → fetch, lokaler Cache > 30 Tage → fetch, sonst skip.

### Live-Fallback: agent_britannica (16.07.)

`rag/agent_britannica.py` ist der zweite Tool-Use-Agent nach `agent_datum`. Wenn der beste Reranker-Score unter `ROUTER_MIN_SCORE` (0.5) liegt — SUSIpedia hat nichts Relevantes — fragt `agent_britannica` die Britannica-API live. Separater Prompt: Gist als Fakten-Anker, LLM-Wissen ergänzt, Antwort in der Fragesprache, Quellenlink am Ende. Der Artikel wird lokal in `docs/wissen/` gecacht — beim nächsten Ingest wird er gechunkt und SUSI beantwortet die Frage dann aus der eigenen Wissensbasis. Inkrementelles Lernen: jede Frage die SUSI nicht beantworten kann macht sie für die Zukunft schlauer.

---

## Aktuelle Query-Pipeline (Stand Juli 2026)

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

## Stand: Juli 2026 · Martin Freimuth

→ Zurück zur Übersicht: `susi_00_übersicht.md`
→ Weiter: `susi_08_produktivbetrieb_infrastruktur.md`