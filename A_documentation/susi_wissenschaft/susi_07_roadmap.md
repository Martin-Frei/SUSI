# 07 — Roadmap
### SUSI Entwicklungsbericht · Stand Juli 2026

---

## Stand heute und was als Nächstes kommt

SUSI ist kein abgeschlossenes Projekt. Es ist ein System in aktivem Betrieb, das parallel weiterentwickelt wird. Die folgende Roadmap unterscheidet zwischen kurzfristigen Maßnahmen, die unmittelbar auf die aktuellen Erkenntnisse reagieren, und längerfristigen Ausbaustufen, die den Charakter des Systems fundamental erweitern.

Die Grundregel für die Priorisierung lautet: **Qualität vor Quantität.** Jede Erweiterung die ein instabiles Fundament voraussetzt wird zurückgestellt bis das Fundament solide ist.

---

## Phase 1 — Stabiles Fundament abschließen *(Q3 2026)*

Die Erkenntnisse aus der Evaluierung und dem externen Review zeigen mehrere offene Punkte die das System vor dem nächsten Ausbauschritt schließen muss.

### SUSIpedia-Qualität vollständig abschließen

Stand 10.06.2026: ca. 85% der 124 Dateien überarbeitet, Retrieval Hit Rate bereits auf 91%. Die verbleibenden ~15% werden heute abgeschlossen — die erwartete Hit Rate danach liegt nahe 100%. Das Ergebnis wird durch Lauf A direkt gemessen: eine Config über alle 40 Testfragen, identisch zu Lauf 8, um den sauberen Vorher-Nachher-Vergleich zu haben.    

✅ **Abgeschlossen (Juni 2026).** Alle 124 Dateien überarbeitet, 617 Chunks in ChromaDB. 
Retrieval Hit Rate von 36% auf 91% gesteigert. Lauf C bestätigt: Dokumentqualität 
war der größte Hebel.

→ *Details: [susi_04_evaluation.md](susi_04_evaluation.md), [susi_08_produktivbetrieb.md](susi_08_produktivbetrieb.md)*

### MMR vs. Similarity evaluieren

Vor dem Cross-Encoder-Reranker wird MMR getestet — hier gibt es bereits Daten aus den Grid-Läufen zum direkten Vergleich mit Similarity Search. Das ist der schnellste nächste Schritt mit dem geringsten Implementierungsaufwand.

✅ **MMR vs. Similarity — abgeschlossen (Lauf C, Juni 2026).** MMR (Ø 2.99) minimal 
schlechter als similarity (Ø 3.01). Unterschied statistisch irrelevant. 
Similarity bleibt Standard.

→ *Details: [susi_08_produktivbetrieb.md](susi_08_produktivbetrieb.md)*

### Cross-Encoder Reranker implementieren

Der Retrieval Check vom 10.06.2026 zeigt dass Hit@1 bei 52.5% liegt aber Hit@5 bei 70%. Der richtige Chunk ist häufig vorhanden — aber nicht an erster Stelle. Ein Cross-Encoder Reranker verbessert die Reihenfolge nach dem Retrieval und kostet kein zusätzliches VRAM da er auf CPU läuft. Zielmetrik: Hit@1 auf 65%+.

Wichtig: das gewählte Modell muss deutsch-kompatibel sein. Kandidat ist `amberoad/bert-multilingual-passage-reranking-msmarco`. Vor dem Einsatz wird ein Sprachkompatibilitäts-Test durchgeführt.

✅ **Cross-Encoder Reranker — abgeschlossen (Juni 2026).** Nach Evaluation über drei 
Modell-Generationen (ms-marco → amberoad/59% → bge-reranker-v2-m3/97%) ist 
bge-reranker-v2-m3 produktiv. Läuft auf CPU, kein VRAM-Verbrauch.

→ *Details: [susi_08_produktivbetrieb.md](susi_08_produktivbetrieb.md)*

### Metriken-Konsistenz im Evaluator absichern

✅ **Teilweise gelöst (Juli 2026).** `DIAG_ZU_QUALITAET` ist als zentrale Konstante in 
`auto_scorer.py` verankert und wird von `grid_run.py` importiert. Die Diagnostic Scale 
wurde auf 0–6 erweitert (Score 6: ValueCheck-Konflikt → Grauzone). `MAX_SCORE = 6` 
steht im Code. Offen: `--nachbewertung` akzeptiert noch 0–2 statt die Diagnostic Scale, 
CSV-Metadaten enthalten `MAX_SCORE` noch nicht als Spalte.

### Asynchronen Worker für Modellwechsel

**`!save`-Befehl implementieren:** Der explizite Speicher-Trigger existiert noch nicht. Die aktuelle Auto-Save-Pipeline speichert automatisch — das Gegenteil des gewünschten Verhaltens. `!save` als Frontend-Befehl implementieren, einen asynchronen Django-Task (Django-Q oder Celery) anschließen, und HTMX Polling für Statusmeldungen ("Lade Modell...", "Erstelle Zusammenfassung...", "Bereit für Review") einbauen. Der Nutzer wird nicht allein gelassen.


❌ Asynchronen Worker für Modellwechsel *(geplant Q3 2026)*
Der `!save`-Befehl ist noch nicht implementiert. Die Planung steht (Kapitel 05 + 06): 
asynchroner Django-Task, `OLLAMA_MAX_LOADED_MODELS=1`, HTMX Polling für Status-Feedback. 
Wird selten ausgelöst (2–3 Mal pro Tag) — kein permanenter Worker nötig.


### Zusätzliche Meilensteine — bereits erledigt (Juni 2026)

✅ **Router implementiert (20.06.2026).** Retrieval-getriebenes Profil-System mit 
6 Kategorien (susi, projekte, lernen, persoenlich, technik, wissen). Reranker-gewichtetes 
Voting auf Chunk-Quellordner. Kein Extra-LLM-Call. `ROUTER_MIN_SCORE = 0.5` als 
Schwellenwert — darunter greift `agent_britannica` als Live-Fallback (seit 21.07.).

✅ **Query Rewriting aktiv (20.06.2026).** Löst Ich-Form-Problem und Folgefragen 
vor dem Retrieval auf. Generisch gehalten für spätere PDF-RAG-Nutzung.

✅ **Fallback-Profil (21.06.2026).** Bei Fragen außerhalb der SUSIpedia greift 
`praezise_hybrid` — erst Kontext prüfen, dann eigenes LLM-Wissen.

✅ **Chat-History im Rewriter (21.06.2026).** Letzte 2 Q/A-Paare werden an den 
Rewriter übergeben. Antworten auf 200 Zeichen gekürzt.

✅ **Frontend: SUSI-Icon + lokale Fonts (20.06.2026).** GDPR-konform, kein 
externer Request.

→ *Details zu allen Punkten: [susi_08_produktivbetrieb.md](susi_08_produktivbetrieb.md)*

### Zusätzliche Meilensteine — Juli 2026

✅ **Britannica-Integration (14.–16.07.).** Batch-Sync (`britannica_sync.py`) und 
Live-Fallback (`agent_britannica.py`) als zweiter Tool-Use-Agent. Gecachte Artikel 
werden beim nächsten Ingest Teil der SUSIpedia — inkrementelles Lernen.

✅ **agent_datum Zweig 2 (17.07.).** Altersberechnung für Entitäten mit genau einem 
Datum im Chunk. Multi-Chunk-Suche, Entity-scoped Section-Split, Typo-Toleranz. 
Bekannte Limitation: Multi-Datum-Chunks, zusammengesetzte Entitäten.

✅ **query.py Refactoring (17.07.).** 861-Zeilen-Monolith in 5 Module aufgeteilt 
(config.py, keywords.py, llm_client.py, utils.py, query.py). `ask_susi_eval()` zu 
dünnem Wrapper — behebt die Duplizierung die den Double-Rewriting-Bug verursacht hatte.

✅ **Ingest-Umbau (17.07.).** `split_by_headings()` ersetzt `RecursiveCharacterTextSplitter`. 
617 → 1176 Chunks. `_split_oversized()` als Fallback für Chunks >1500 chars (21.07.).

✅ **Reranker-Performance (21.07.).** Monster-Chunks als Root Cause für 120s-Reranking 
identifiziert und durch `_split_oversized()` behoben. CrossEncoder auf CPU fixiert, 
Warmup-Singleton. Ergebnis: 120s → 3–5s.

✅ **Lauf G (15.07.).** ValueCheck False Positives entdeckt, Diagnostic Score 6 als Fix. 
Bereinigte Korrektheit ~93.8%, Router-Accuracy 67.5%.

→ *Details: [susi_08_produktivbetrieb.md](susi_08_produktivbetrieb.md)*
---

## Phase 2 — 3-stufiges Speichermodell implementieren *(Q4 2026)*

Das Konzept des Human-in-the-Loop Speichermodells ist ausgearbeitet (vgl. Kapitel 05). 
Die technischen Voraussetzungen sind mit bge-reranker-v2-m3 (97% Korrektheit) und dem 
produktiven Router gegeben. Die Implementierung folgt in dieser Reihenfolge:

**Stufe 1 — SQLite Kurzzeitgedächtnis:** Der Chatverlauf wird persistent in einer lokalen SQLite-Tabelle gehalten. Kein Datenverlust bei Ollama-Crashes. Trigger: einzig der explizite `!save`-Befehl.

**Stufe 2 — Automatisierter Türsteher:** Der Markdown-Entwurf durchläuft einen mehrsprachigen Cross-Encoder-Check bevor er die SUSIpedia erreicht. Halluzinierter Inhalt wird abgefangen. Der Modellwechsel passiert asynchron im Hintergrund — `OLLAMA_MAX_LOADED_MODELS=1` verhindert dass beide Modelle gleichzeitig VRAM belegen.

**Frontend-Feedback während des Speicherns:** Während der Background-Task läuft zeigt das HTMX-Frontend eine kleine Statusanzeige — "Lade Modell...", "Erstelle Zusammenfassung...", "Prüfe auf Halluzinationen...", "Bereit für Review". Der Nutzer wird nicht allein gelassen. Das kostet keine Architektur-Komplexität — HTMX Polling auf einen Status-Endpoint reicht vollständig aus.

**Stufe 3 — SusiInbox im Dashboard:** Freigegebene Entwürfe landen in einer Django-Tabelle und werden über das bestehende HTMX-Frontend in einem One-Click-Review angezeigt. Abgelehntes Material wandert in `RejectedSaves` als automatisch wachsendes Negativ-Trainingsset.

---

## Phase 3 — Retrieval-Architektur erweitern *(2027)*

Mehrere offene Fragen aus der Evaluierung deuten auf strukturelle Grenzen der aktuellen Retrieval-Architektur hin. Phase 3 beginnt erst wenn Phase 2 abgeschlossen ist und der Cross-Encoder-Reranker mindestens einen vollständigen Evaluierungslauf mit messbarer Verbesserung gezeigt hat. Die Gate-Bedingung: Hit@1 über 65% und das 3-stufige Speichermodell hat mindestens 30 validierte Saves ohne erkannte Halluzination verarbeitet.

**Reihenfolge innerhalb Phase 3:** Kategorie-spezifische Konfiguration, dann Hybrid Search — nur wenn die anderen Maßnahmen das Projekte-Problem nicht vollständig lösen.

### PDF-RAG *(geplant)*

Beliebige PDFs als temporären ChromaDB-Index einlesen und gezielt befragen. 
Query Rewriting ist bereits generisch gehalten (kein Overfitting auf Martin). 
Benötigt: separater Index pro Dokument, Session-Kontext für Folgefragen.

### Hybrid Search

Die GMM-Retrieval-Misses entstehen weil "Pipeline", "Deploy" und "Run" als allgemeine DevOps-Begriffe keinen starken semantischen Vektor erzeugen. Keyword-basierte BM25-Suche würde hier helfen. ChromaDB unterstützt kein natives Hybrid Search — die Entscheidung lautet: BM25-Workaround mit eigenem Preprocessing, oder Migration zu Weaviate bzw. Qdrant. Diese Entscheidung wird erst getroffen wenn Cross-Encoder und kategorie-spezifische Configs ihren vollen Effekt gezeigt haben.

### Kategorie-spezifische Konfiguration

Lernen hat 100% Hit Rate, Projekte 30% — eine einheitliche Konfiguration für beide ist möglicherweise nicht optimal. Unterschiedliche `top_k`-Werte oder Retrieval-Strategien pro Ordner-Kategorie wären ein natürlicher nächster Schritt. Das setzt eine stabilere Gesamt-Hit-Rate als Basis voraus.

✅ **Kategorie-spezifische Konfiguration — gelöst durch Router (Juni 2026).** 
Der Retrieval-getriebene Router weist jeder Kategorie ein eigenes Profil mit 
spezifischen top_k-, top_n- und Temperature-Werten zu. Lernen nutzt llama3.1:8b 
mit top_k=9, Projekte nutzen qwen2.5-coder:7b mit top_k=7. Keine manuelle 
Konfiguration nötig — die SUSIpedia-Ordnerstruktur steuert die Zuordnung automatisch.

→ *Details: [susi_08_produktivbetrieb.md](susi_08_produktivbetrieb.md)*
---

## Phase 4 — Edge Deployment und physische Integration *(langfristig)*

Die lokale Philosophie von SUSI schließt Cloud-Deployment aus — eröffnet aber eine andere Richtung: Edge-Deployment auf kleiner Hardware.

### Raspberry Pi 5 als MCP-Server

Kleine Modelle (1B–3B Parameter), quantisiert und fine-tuned auf SUSIpedia-Wissen, könnten auf einem Raspberry Pi 5 (8GB) als MCP-Server laufen. Anwendungsfälle:

- Sprachsteuerung über Whisper (lokale Speech-to-Text-Inferenz via whisper.cpp — Inferenz-Tasks müssen sequenziell geschaltet werden da der Pi 5 unter paralleler LLM- und Whisper-Last einbricht)
- GPIO-Integration für Smart Home (Home Assistant Anbindung)
- Personen- oder Szenen-Erkennung über angebundene Kamera

Dieser Ausbauschritt ist bewusst langfristig eingeordnet — er setzt eine stabile und wartbare Kern-Architektur voraus.

### Unternehmenseinsatz als Konzept

Eine Erkenntnis aus der Entwicklung: SUSI löst ein Problem das nicht nur Privatpersonen haben. Unternehmen unter DSGVO, AI Act und Geschäftsgeheimnisgesetz brauchen lokale KI-Lösungen — und bestehende Alternativen wie Microsoft Copilot sind Cloud-gebunden.

Das SUSI-Konzept (RAG-basiert, vollständig lokal, model-agnostisch, Human-in-the-Loop für Wissenskuration) ist auf Unternehmensumgebungen übertragbar. Dieses Konzept wird parallel weitergedacht — nicht als Produktplan sondern als konzeptionelle Richtung.

---

## Was nicht auf der Roadmap steht

Ebenso wichtig wie das was gebaut wird ist das was bewusst nicht gebaut wird:

**Kein Fine-Tuning des Basismodells für jetzt.** Fine-Tuning stabilisiert domänenspezifisches Wissen — aber es macht das System modellgebunden. Solange die SUSIpedia noch wächst und das Retrieval noch optimiert wird ist RAG die flexiblere und iterierbarere Lösung.

**Keine automatische Wissensgewinnung ohne Human-in-the-Loop.** Die vier Sackgassen aus Kapitel 05 haben gezeigt, wohin vollständige Automatisierung führt. Jede Erweiterung, die autonomes Schreiben in die SUSIpedia ermöglicht, wird erst nach vollständiger Implementierung der Validierungs-Stufen aus dem 3-stufigen Speichermodell in Betracht gezogen.

---

## Der Kern bleibt gleich

Alle Phasen dieser Roadmap bauen auf derselben Grundentscheidung auf: **die Wissensbasis gehört dem Nutzer**. Kein Modell-Update, kein API-Wechsel, kein Cloud-Anbieter kann dieses Wissen entfernen oder unzugänglich machen. Das ist keine technische Einschränkung — es ist das Designprinzip.

Die in Kapitel 06 dokumentierten Grenzerfahrungen bleiben bestehen und werden durch diese Roadmap nicht aufgehoben — sie sind die Grundlage auf der die Phasen priorisiert wurden.

---

→ *Zurück zur Übersicht: [susi_00_übersicht.md](susi_00_übersicht.md)*  
→ *Produktivbetrieb: [susi_08_produktivbetrieb.md](susi_08_produktivbetrieb.md)*   
*Stand: Juli 2026 · Martin Freimuth*