# 02 — Systemarchitektur
### SUSI Entwicklungsbericht · Stand Juli 2026

---

## Das unveränderliche Grundprinzip

SUSI folgt dem RAG-Prinzip (Retrieval-Augmented Generation). Das Grundprinzip hat sich seit dem ersten Tag nicht geändert und wird sich auch nicht ändern — es ist die architektonische Basis auf der alles andere aufbaut:

```
Frage des Nutzers
       ↓
detect_language()                                    [lokal, LLM, num_ctx=128]
       ↓
agent_datum Guard: Reine Kalenderfrage?              [lokal, deterministisch]
  ├─ Ja (mode=auto|manuell, lang=de) → Python datetime → Antwort ~1ms
  └─ Nein → normale Pipeline weiter
       ↓
Query Rewriting löst Ich-Form und Folgefragen auf   [lokal, LLM]
       ↓
Embedding-Modell wandelt Frage in Vektor um         [lokal]
       ↓
ChromaDB sucht die ähnlichsten Wissens-Chunks       [lokal]
       ↓
Reranker (bge-reranker-v2-m3) sortiert Top 3        [lokal, CPU]
       ↓
Router: Reranker-Score-Summe pro Kategorie → Profil  [lokal]
       ↓
Kontext + Original-Frage + System-Prompt
       ↓
LLM generiert die Antwort                           [lokal]
       ↓
Antwort an den Nutzer
```

Alle Komponenten laufen lokal. Kein einziger Byte verlässt das System.

---

## Stack-Entscheidungen — und warum sie so gefallen sind

### Django statt Flask

Django wurde über Flask gewählt weil die langfristige Vision von Anfang an ein vollständiges Web-Interface war — nicht nur ein Skript das in der Konsole läuft. Django bringt ORM, Admin-Interface, Template-System und HTMX-Kompatibilität von Haus aus mit. Stabilität vor Novelty.

### ChromaDB als Vector Store

ChromaDB hat einen entscheidenden Vorteil für ein Ein-Personen-Projekt: Zero-Dependency. Keine externe Datenbank, kein Service der laufen muss, keine Konfiguration. Die Datenbank ist eine lokale Datei.

Die bekannte Schwäche ist kein natives Hybrid Search — also keine Kombination aus klassischer Keyword-Suche (BM25) und Vektorähnlichkeit. Ob das ein Problem ist zeigt der Evaluierungslauf.

→ *Entscheidung ChromaDB vs. Weaviate/Qdrant: abhängig von Evaluierungsergebnissen — siehe [susi_04_evaluation.md](susi_04_evaluation.md)*

### Ollama als LLM-Server

Ollama läuft als lokaler Inferenz-Server auf Port 11434 und macht den Modellwechsel trivial — ein anderer Modellname in der Config und das System läuft mit einem anderen LLM. Das ist die praktische Umsetzung des Prinzips "das Modell ist austauschbar".

### LangChain als Framework

LangChain verbindet Embedding-Modell, ChromaDB und LLM mit minimalem Boilerplate. Der Trade-off ist eine Abhängigkeit von einem Framework das sich schnell weiterentwickelt — bisher kein Problem, aber ein bekanntes Risiko.

### susi_config.yaml — Single Source of Truth

Es werden alle Parameter zentral in `rag/susi_config.yaml` verwaltet.
Ingest, Query und Views lesen alle aus dieser Config — keine hardcodierten Werte mehr.
Modellwechsel, Chunk-Größen oder Prompt-Änderungen sind ein Edit in einer Datei.

---

## Die Ingestion Pipeline — differenziell von Anfang an

`ingest.py` implementiert eine differenzielle Update-Strategie die sich seit dem ersten Tag nicht geändert hat:

```
Alle .md Dateien in docs/ scannen
       ↓
MD5-Hash jeder Datei berechnen
       ↓
Vergleich mit gespeicherten Hashes (chroma_db/doc_hashes.json)
       ↓
Nur neue oder veränderte Dateien verarbeiten
       ↓
Alte Chunks der geänderten Datei aus ChromaDB löschen
       ↓
Neue Chunks generieren und per Upsert einfügen
       ↓
Hashes aktualisieren
```

Das ist effizient weil bei 50+ Dateien nicht alles neu indexiert wird wenn eine Datei geändert wird. Nur was sich wirklich geändert hat wird neu verarbeitet.

---

## Parameter — was sich geändert hat und warum

### Embedding-Modell

**Stand März 2026:** `nomic-embed-text`  
Gewählt wegen 8.000 Token Kontextfenster und einfacher Verfügbarkeit via Ollama. Läuft auf der CPU damit der VRAM der GPU exklusiv dem LLM zur Verfügung steht.

**Stand Mai 2026:** `bge-m3` in Evaluation  
bge-m3 gilt als stärkster Allrounder mit besserer deutscher Sprachverarbeitung. Im Retrieval Check (10.06.2026) wurde bge-m3 als aktives Embedding-Modell verwendet.

→ *Endgültige Entscheidung nach Grid-Lauf — siehe [susi_04_evaluation.md](susi_04_evaluation.md)*

### Chunk-Größe

**Stand März 2026:** `chunk_size=300, overlap=50` — einheitlich für alle Dateien

**Geplant aber nicht implementiert (April 2026):** Differenzierte Chunk-Größen — 300/50 für persönliche Inhalte, 500/100 für technische Inhalte. Die Logik war inhaltlich sinnvoll: technische Konzepte brauchen mehr Kontext als kurze persönliche Fakten. In der Praxis wurde die Differenzierung nicht in `ingest.py` umgesetzt weil die Evaluierungsläufe zeigten dass eine einheitliche große Chunk-Größe (1000) kategorieübergreifend bessere Ergebnisse liefert als eine differenzierte kleine.

**Stand Evaluation (Mai/Juni 2026):** `chunk_size=1000, overlap=50` wird im Grid-Lauf getestet — deutlich größere Chunks um mehr Kontext pro Retrieval zu liefern.

→ *Optimaler Wert nach Grid-Lauf — siehe [susi_04_evaluation.md](susi_04_evaluation.md)*

### Top-K (Anzahl retrievter Chunks)

**Stand März 2026:** `k=8` — in `query.py` fest verdrahtet

**Problem erkannt (April 2026):** Bei k=8 wurden Chunks aus thematisch unverwandten Dokumenten kombiniert. Fragen über persönliche Themen retrievten gleichzeitig Projektdaten. Ursache: zu hoher k-Wert ohne Score-Threshold.

**Stand Evaluation (Mai/Juni 2026):** k=3, 5, 8, 10 werden systematisch verglichen.

→ *Optimaler Wert nach Grid-Lauf — siehe [susi_04_evaluation.md](susi_04_evaluation.md)*

### Retrieval-Algorithmus

**Stand März 2026:** `similarity_search` — reine Vektorähnlichkeit

**Stand Evaluation (Mai/Juni 2026):** `similarity` vs. `MMR` (Maximal Marginal Relevance) werden verglichen. MMR bestraft redundante Chunks und liefert bei thematisch überlappenden Dokumenten potenziell bessere Ergebnisse.

→ *Ergebnisse nach Grid-Lauf — siehe [susi_04_evaluation.md](susi_04_evaluation.md)*

### LLM

**Stand März 2026:** `mistral:7b` — erster Test, allgemeiner Assistent

**Stand April 2026:** Wechsel zu `qwen2.5-coder:7b` — präziser bei technischen Inhalten, weniger Halluzinationen bei strukturierten Antworten. Außerdem ein konkretes Problem mit Mistral: das Modell wechselte trotz expliziter Prompt-Anweisung bei längeren Antworten zur Höflichkeitsform ("Sie" statt "du"). Prompt-Verschärfung half, löste das Problem aber nicht dauerhaft.

**Stand Evaluation (Mai/Juni 2026):** qwen2.5-coder:7b und llama3.1:8b wurden verglichen. `gemma2:9b` und `mistral-nemo:12b` wurden in frühen Plänen erwähnt aber nie formal evaluiert.

**Stand Produktivbetrieb (Juli 2026):** `qwen2.5-coder:7b` ist primäres Modell (Fakten, Code, alle Profile außer lernen und persoenlich). `llama3.1:8b` für Profil `lernen`. `qwen2.5:7b` für Profil `persoenlich` (multilingual). `qwen3:8b` und `qwen3:14b` getestet in Lauf E — kein signifikanter Vorteil gegenüber qwen2.5-coder:7b.

→ *Details: [susi_04_evaluation.md](susi_04_evaluation.md), [susi_08_produktivbetrieb.md](susi_08_produktivbetrieb.md)*

---

## System-Prompt — profilspezifisch via Config

Der System-Prompt ist nicht mehr hardcodiert in `query.py`. Alle Prompts sind in `rag/susi_config.yaml` als benannte Varianten definiert und werden profilabhängig geladen. Das aktive Profil bestimmt welcher Prompt verwendet wird — `praezise_neu` für susi/projekte/technik, `praezise_hybrid` für persoenlich und als Fallback.

`praezise_hybrid` ist die ausgewogenste Variante: zuerst den Kontext prüfen, bei fehlenden Informationen auf eigenes LLM-Wissen zurückgreifen mit dem Hinweis `[Basierend auf meinem allgemeinen Wissen...]`. Das vermeidet zu viele "Dazu habe ich nichts"-Antworten ohne unkontrolliert zu halluzinieren.

Die Sprachinstruktion (`lang_instruction`) wird dynamisch generiert und erscheint direkt vor "Antwort:" im Prompt — nicht am Anfang. Diese Positionierung ist wichtig: LLMs respektieren die Sprachanweisung zuverlässiger wenn sie unmittelbar vor der Generierung steht.

---
## Neue Pipeline-Stufen *(Produktivbetrieb Juni 2026)*

### Query Rewriting

Embedding-Modelle können keine Coreference auflösen — „Ich bin Martin. Wo wohne ich?"
findet nicht den richtigen Chunk, weil „ich" und „Martin" im Vektorraum nicht verknüpft sind.

Die Lösung: Ein LLM-Call schreibt die Frage vor dem Retrieval um:   
"Ich bin Martin. Wo wohne ich?" → "Martin Freimuth wo wohne ich?"



ChromaDB sucht mit der umgeschriebenen Frage. Ans Antwort-LLM geht die Original-Frage
für eine natürliche Antwort. Ergänzt wird das durch `ich_bin_martin.md` — zwei Chunks
mit Selbstreferenz-Sätzen in der SUSIpedia. Der Rewriter ist generisch gehalten und
kann über `query_rewriting.active` in der Config deaktiviert werden.

### Reranker — bge-reranker-v2-m3

Nach dem Retrieval bewertet ein Cross-Encoder-Modell die Chunks neu und gibt die besten
top_n=3 ans LLM weiter. Läuft auf CPU, verbraucht kein VRAM.

Die Modell-Wahl war eine Evolution: ms-marco (English-only) → amberoad (59%, aktiv schädlich)
→ bge-reranker-v2-m3 (97%). Erkenntnis: Ein schlechter Reranker ist schlimmer als gar keiner.

### Router — Retrieval-getriebenes Profil-System

Statt eines fixen Parameter-Satzes wählt ein Router das optimale Profil basierend auf
der SUSIpedia-Struktur:

Frage rein    
→ Retrieval     
→ Reranker sortiert Top 3    
→ Router: woher kommen die Chunks? (Ordnerpfad)   
→ Reranker-gewichtetes Voting    
→ Profil gewinnt


Fünf Profile: susi, projekte, lernen, persoenlich, technik    
→ jedes mit eigenem LLM, top_k, top_n und Temperature.     
Bei Fragen außerhalb der SUSIpedia greift ein Fallback-Profil.

*Details: [susi_08_produktivbetrieb.md](susi_08_produktivbetrieb.md)*

---

### Auto-Save Pipeline *(deaktiviert Mai 2026)*

Die Pipeline war vollständig implementiert und lief produktiv:
- `worth_saving()` — regelbasierter Filter
- `susi_evaluates()` — LLM bewertet ob eine Konversation speichernswert ist
- `get_suggestions()` — Keyword-Router schlägt Zielordner vor
- `create_summary()` — LLM erstellt kompakte Zusammenfassung
- `save_to_susipedia()` — schreibt `.md` Datei und ruft `ingest.py` auf

Der Ansatz war konzeptionell interessant — SUSI lernt durch strukturierte Dokumentation, 
nicht durch Gradientenabstieg. Das Problem: das System schreibt eigene Halluzinationen 
ins Langzeitgedächtnis zurück. Eine zerstörerische Feedback-Schleife, die erst durch 
formale Evaluation sichtbar wurde.

**Aktueller Status:** Die Pipeline wurde im Mai 2026 deaktiviert. Der Code bleibt nach dem Prinzip "kein Abriss ohne Ersatz" in `query.py` erhalten. Das Fundament der neuen 3-stufigen Architektur steht: bge-reranker-v2-m3 (97% Korrektheit) produktiv, SQLite-Persistenz mit `Chat`, `Message` und `QueueItem` seit 25.06.2026 aktiv, HitL-Queue-Button an jeder Antwort. Asynchroner Worker und `!save`-Kommando folgen in Q3 2026.

→ *Vollständige Analyse: [susi_05_sackgassen.md](susi_05_sackgassen.md)*  
→ *Reranker-Evolution: [susi_08_produktivbetrieb.md](susi_08_produktivbetrieb.md)*

---

## Lernparadigmen — wie SUSI "lernt" und wohin das führt

Dieser Abschnitt ist strukturell wichtig weil er einen fundamentalen Unterschied erklärt der im KI-Kontext oft verwischt wird: es gibt verschiedene Arten wie ein System "lernen" kann — und sie haben völlig unterschiedliche Konsequenzen.

### Gradientenabstieg — wie klassische Modelle lernen

Gradientenabstieg ist der mathematische Mechanismus hinter dem Training neuronaler Netze. Das Modell macht einen Fehler, berechnet wie groß der Fehler ist, passt seine internen Gewichte minimal an — und wiederholt das millionenfach. So entstand qwen2.5-coder:7b. So entstehen alle großen Sprachmodelle.

Das Ergebnis sind Milliarden von Gewichten (Zahlen) die das gesamte Wissen des Modells kodieren. Dieses Wissen ist eine Black Box — nicht direkt lesbar, nicht gezielt änderbar, nicht reversibel ohne neu zu trainieren.

### Wie SUSI aktuell lernt — RAG statt Gradientenabstieg

SUSI verändert keine Modellgewichte. Das Modell selbst bleibt unberührt. SUSI lernt stattdessen durch strukturierte Wissensverwaltung:

```
Neue Erkenntnis entsteht
       ↓
Wird als .md Datei in SUSIpedia geschrieben
       ↓
ingest.py indexiert den neuen Chunk in ChromaDB
       ↓
Beim nächsten Retrieval findet das System diesen Chunk
       ↓
SUSI kann die Frage jetzt beantworten
```

| | Gradientenabstieg | SUSI (RAG) |
|---|---|---|
| Was ändert sich? | Modellgewichte | Wissensbasis |
| Wie? | Mathematisch, automatisch | Manuell, strukturiert |
| Transparent? | Black Box | Vollständig lesbar |
| Reversibel? | Nein | Ja — Datei löschen |
| Kontrollierbar? | Kaum | Vollständig |

Das ist ein bewusstes Designprinzip: transparentes, kontrollierbares Wissen statt Black-Box-Training.

### Fine-Tuning — die nächste Stufe *(Phase 3)*

Es gibt einen dritten Weg der beide Ansätze verbindet: **Fine-Tuning**. Dabei werden die originalen Modellgewichte als Kopie eingefroren (Base Model), und das Modell wird auf den eigenen Daten weitertrainiert. Das Ergebnis ist ein spezialisiertes Modell das domänenspezifisches Wissen direkt in den Gewichten trägt.

Das Hauptrisiko ist **katastrophales Vergessen** — das Modell lernt die neuen Inhalte, vergisst dabei aber allgemeines Wissen das vorher drin war.

### LoRA — der praktische Weg zum Fine-Tuning *(Phase 3)*

Die elegante Lösung für das Vergessen-Problem heißt **LoRA (Low-Rank Adaptation)**. Statt die kompletten Gewichte zu verändern werden kleine spezialisierte Adapter-Module trainiert die auf das Base Model aufgesetzt werden:

```
Base Model (frozen, ~4GB)
       ↓
Für jedes Thema ein eigenes Adapter-Modul
       ↓
susi_lora_spv2.bin         → StockPredict Wissen
susi_lora_bewerbung.bin    → Bewerbungs-Kontext
susi_lora_persoenlich.bin  → Persönliche Daten
susi_lora_gmm.bin          → GMM Projekt
       ↓
SPV2-Tag → Base + SPV2-Adapter laden
Bewerbungstag → Base + Bewerbungs-Adapter laden
```

| | Volles Fine-Tuning | LoRA Adapter |
|---|---|---|
| Größe | Komplette Gewichte (~4GB) | Nur Adapter (~50MB) |
| Trainingszeit | Stunden | Minuten |
| Katastrophales Vergessen | Hohes Risiko | Minimales Risiko |
| Adapterwechsel | Neu laden = langsam | Tauschen = schnell |
| Auf RTX 3090 machbar? | Grenzwertig | ✅ Ja |

Der natürliche Rhythmus wäre ein **wöchentlicher automatischer Lauf**: neue SUSIpedia-Inhalte der Woche als Trainingsdaten, LoRA-Adapter pro Thema aktualisieren, nächste Woche mit aktualisiertem Wissen starten. Auf der RTX 3090 realistisch in 10–30 Minuten pro Adapter.

**Die ideale Kombination langfristig:**

> **LoRA Fine-Tuning für stabiles Domänenwissen** + **RAG für dynamische, täglich updatebare Inhalte**

LoRA ist kein neues Konzept — es taucht in der Literatur regelmäßig auf. Der Moment wo es vom gelesenen Begriff zum verstandenen Werkzeug wird ist genau der Moment der durch Bauen entsteht, nicht durch Lesen.

*→ LoRA-Integration ist klar Phase 3 — erst wenn RAG-Optimierung abgeschlossen ist macht Fine-Tuning auf einer sauberen Wissensbasis Sinn.*

---

## Aktuelle Architektur auf einen Blick *(Stand Juli 2026)*

| Komponente | |
|------------|-----------------|
| Embedding | bge-m3 |
| Vector Store | ChromaDB (617 Chunks) |
| Chunk-Größe | 1000/50 |
| Retrieval | similarity |
| Reranker | BAAI/bge-reranker-v2-m3 (CPU, 97%) |
| Router | Retrieval-getrieben, 5 Profile |
| Language Detection | aktiv (ISO 639-1, num_ctx=128) |
| Query Rewriting | aktiv (Ich-Form, Folgefragen, keine Übersetzung Fachbegriffe) |
| Tool Use | agent_datum (Kalender-Guard, ~1ms, kein LLM) |
| LLM primär | qwen2.5-coder:7b (susi, projekte, technik) |
| LLM sekundär | llama3.1:8b (lernen) |
| LLM multilingual | qwen2.5:7b (persoenlich, Fallback) |
| Modus | AUTO / MANUELL / CODING Toggle |
| Config | susi_config.yaml (Single Source of Truth) |
| Chat-History | SQLite (Chat, Message, QueueItem) seit 25.06.2026 |
| Auto-Save | deaktiviert (Mai 2026) — HitL-Button aktiv, async Worker Q3 2026 |

---

*→ Zurück zur Übersicht: [susi_00_Übersicht.md](susi_00_übersicht.md)*  
→ *Weiter: [susi_03_susipedia.md](susi_03_susipedia.md)*  
→ *Produktivbetrieb: [susi_08_produktivbetrieb.md](susi_08_produktivbetrieb.md)*  
*Stand: Juli 2026 · Martin Freimuth*