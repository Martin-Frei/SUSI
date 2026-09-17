# SUSI — Selbständige und Schlaue Intelligenzbestie

> Vollständig lokaler, DSGVO-konformer KI-Assistent mit RAG-Wissensbasis.  
> Persönliche Daten verlassen niemals den lokalen Rechner.

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6B35?style=for-the-badge&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logoColor=white)

**97% Antwort-Korrektheit · 5.860 automatisierte Eval-Runs · Latenz halbiert: 26s → ~12s · 0.001s deterministisch statt 8s LLM-Halluzination**

---

## Was ist SUSI?

SUSI ist ein persönlicher KI-Assistent der vollständig lokal läuft — keine Cloud, keine Datenweitergabe. Die Wissensbasis heißt **SUSIpedia**: eine wachsende Sammlung von Markdown-Dateien mit Projekten, Lernnotizen und persönlichem Kontext.

Das System kombiniert **Retrieval-Augmented Generation (RAG)** mit lokalen LLMs über Ollama. SUSIpedia ist der eigentliche Kern — SUSI ist modell-agnostisch und funktioniert mit jedem Ollama-Modell.

SUSI entstand aus einer einfachen Überzeugung: Ein persönlicher Assistent der alles über mich weiß gehört nicht in die Cloud. Deshalb läuft alles lokal — die spannende Ingenieursfrage ist, wie viel Qualität man aus 7B-Modellen auf Consumer-Hardware herausholen kann. Antwort: 97%.

**Einzige Ausnahme:** Die Britannica-Integration (Stufe 1.3) ruft kuratierte Enzyklopädie-Artikel per API ab — ausgehende Anfragen enthalten nur den Themennamen, nie persönliche Daten. Das Wissen wird lokal indexiert.

---

## SUSI in Action

![SUSI Chat Screenshot](screenshots/SUSI_Chat.jpg)

Drei Fragen, drei unterschiedliche Mechanismen:

| Frage | Mechanismus | Zeit | Antwort |
|---|---|---|---|
| „Wie alt ist SUSI?" | Zweig 2: Datum aus Chunk, Python rechnet | 6.69s | SUSI ist 3 Monate (114 Tage) alt ✅ |
| „Wie viele Tage bis zum 29. November?" | Zweig 1: Python datetime direkt | **0.001s** | 140 Tage ✅ |
| „Wieviele Tage bis zu Martin Geburtstag?" | Zweig 1: Geburtstags-Anker, Python | **0.001s** | 140 Tage ✅ |

**Was das bedeutet:** Datumsfragen werden nicht mehr dem LLM überlassen — LLMs halluzinieren bei Rechenaufgaben strukturell. Python datetime ist deterministisch. Der `agent_datum` fängt diese Fragen ab bevor das LLM sie falsch beantworten kann.

---

## Kernarchitektur

```
Frage rein
     ↓
Spracherkennung (langdetect, ~0.002s)
     ↓
agent_datum Guard ──── Kalenderfrage? ────► Python datetime → Antwort (~0.001s)
     │ nein
     ▼
Rewriter-Bypass ─── Erste Frage oder >300 Zeichen? ──► Query unverändert weiter
     │ nein
     ▼
Query Rewriting (Coreference-Auflösung, letzte 2 Q/A)
     ↓
ChromaDB Retrieval (bge-m3, top-k Chunks)
     ↓
bge-reranker-v2-m3 (Top-n behalten, 3–5s auf CPU)
     ↓
agent_britannica ── Score ≤ 0.5? ────► Britannica/Wikipedia Fallback
     │ nein
     ▼
agent_datum Zweig 2 ── Laufzeitfrage? ───► Datum aus Chunk, Python rechnet
     │ nein                                 Fakt ins Prompt injiziert
     ▼
Retrieval-getriebener Router
     ↓
LLM generiert Antwort (qwen2.5-coder:7b / llama3.1:8b / qwen2.5:7b)
     ↓
Frontend (Django + HTMX, tok/s + Quelldateien)
```

### Speed-Optimierungen (Juli/August 2026)

| Phase | Vorher | Nachher | Fix |
|---|---|---|---|
| Spracherkennung | 4–12s (LLM) | 0.002s | `langdetect` Library statt Ollama-Call |
| Query Rewriting | 5–9s (immer) | 0s oder 5–9s | Bypass bei erster Frage oder >300 Zeichen |
| Reranking | 100–130s | 3–5s | Duplikates Warmup entfernt, CPU-Pinning, Chunk-Split |
| **Gesamt** | **~26–30s** | **~10–15s** | |

---

## Retrieval-getriebener Router

Das Herzstück von SUSI: Nicht Keyword-Matching sondern die **SUSIpedia-Ordnerstruktur selbst** bestimmt welches LLM und welche Parameter genutzt werden.

```python
# Beispiel Voting (reranker-score-gewichtet):
# Chunk 1 (score=0.92) aus docs/coding/  → projekte: 0.92
# Chunk 2 (score=0.71) aus docs/lernen/  → lernen:   0.71
# Chunk 3 (score=0.68) aus docs/lernen/  → lernen:  +0.68 = 1.39  ← Gewinner
```

| Profil | LLM | Einsatz |
|---|---|---|
| susi | qwen2.5-coder:7b | SUSI-Selbstwissen |
| projekte | qwen2.5-coder:7b | Code-Projekte |
| lernen | llama3.1:8b | Lernmaterial, Konzepte |
| persoenlich | qwen2.5:7b | Persönliches, Job |
| technik | qwen2.5-coder:7b | Hardware, Tools |
| wissen | qwen2.5:7b | Britannica/Wikipedia Wissensbasis |

**Fallback** bei max. Reranker-Score ≤ 0.5: Profil `persoenlich` oder `agent_britannica` Fallback.

---

## Agenten-Architektur

SUSI nutzt deterministische Agenten die Fragen vor oder nach der RAG-Pipeline abfangen. Prinzip: Wenn die Antwort berechenbar ist, wird kein LLM gefragt.

| Agent | Funktion | Latenz |
|---|---|---|
| `agent_datum` | Kalenderfragen (Zweig 1: direkt, Zweig 2: Datum aus Chunk) | ~0.001s |
| `agent_pedia` | Wikipedia-Integration, Heading-Konvertierung | variabel |
| `agent_britannica` | On-demand Britannica-Fetch bei Reranker-Score ≤ 0.5 | variabel |

**Namenskonvention:** `agent_*.py` für alle Werkzeuge. Geplant: `agent_rechner` (Mathe), `agent_meta` (SUSI-Config-Fragen), `agent_duplikat` (SUSIpedia-Duplikatprüfung).

---

## Evaluation Framework

SUSI hat ein vollständiges RAG-Evaluierungs-Framework unter `tools/evaluation/`:

**Vier-Stufen-Pipeline:** Auto-Scorer (Diagnostic Scale 0–6) → ValueCheck (deterministische Zahlen/Datums-Prüfung) → RAGAS (Grauzonen) → Haiku-Judge (verbleibende Unklarheiten)

### Ergebnisse

| Lauf | Fragen | Runs | Ergebnis | Highlight |
|---|---|---|---|---|
| Lauf D | 293 | 800 | **97.1% Korrektheit** | bge-reranker-v2-m3 vs. amberoad: 97% vs. 59% |
| Lauf E | 293 | 586 | 96.9% (qwen3:8b) | Thinking=on vs. off: 0.011 Punkte Unterschied |
| Lauf F | 293 | 293 | Bug gefunden | Doppeltes Rewriting kostete 16 Prozentpunkte |

**Wichtigste Erkenntnisse:**
- Die größte Qualitätsverbesserung kam nicht durch Modell-Tuning sondern durch bessere Dokumentstruktur — Retrieval Hit Rate von **36% auf 91%** allein durch SUSIpedia-Formatierung und Chunk-Size-Optimierung.
- Fine-Tuning auf SUSIpedia-Daten ist ungeeignet: zu wenig Chunks, Living Knowledge Base — RAG ist architektonisch überlegen weil das Wissen extern, auditierbar und ohne Retraining aktualisierbar bleibt.
- Parameterdifferenzen zwischen Modellkonfigurationen sind minimal im Vergleich zur Dokumentqualität.

---

## Tech Stack

| Komponente | Technologie |
|---|---|
| Backend | Django |
| Frontend | HTMX (AUTO/MANUELL-Modus, Chat-History, HitL-Queue) |
| LLM primär | Ollama – `qwen2.5-coder:7b` |
| LLM sekundär | Ollama – `llama3.1:8b`, `qwen2.5:7b` |
| LLM optional | `qwen3:8b`, `qwen3:14b` (Thinking-Modus) |
| Embeddings | `BAAI/bge-m3` |
| Reranker | `BAAI/bge-reranker-v2-m3` (CPU-pinned, Singleton) |
| Vector Store | ChromaDB (lokal, HNSW auf CPU) |
| Orchestrierung | LangChain |
| Spracherkennung | `langdetect` (55 Sprachen, <1ms) |
| Wissensbasis | SUSIpedia – Markdown-Dateien, 617+ Chunks |
| Externe Quellen | Britannica API (Gist), Wikipedia |
| Konfiguration | `susi_config.yaml` – Single Source of Truth |
| Tool Use | `agent_datum`, `agent_pedia`, `agent_britannica` |
| Debug-System | `rag/debug.py` — Logger, Timer, TimingCollector, rotierende Logdateien |
| Performance | `keep_alive: 300` — Modelle bleiben 5 Min. im VRAM, kein 40s Cold-Start |

**Hardware:** AMD Ryzen 9 5900X · 32 GB RAM · RTX 4070 12 GB VRAM

---

## SUSIpedia — Philosophie

```
Eine .md Datei    = Ein klar abgegrenztes Thema
Ein ## Abschnitt  = Wird zu eigenem ChromaDB-Chunk
Max 3 Ebenen      = Lebensbereich → Projekt → Aspekt
```

**Wichtigste Regel:** Immer vollständige Sätze statt kompakter Listen.
Der erste Satz jedes `##` Abschnitts muss den vollständigen Kontext enthalten
damit der Chunk ohne das restliche Dokument verständlich ist.

```
❌  contamination=0.05, n_estimators=100
✅  Der Isolation Forest verwendet eine Contamination von 0.05
    was einer erwarteten Anomalierate von 5 Prozent entspricht.
```

---

## Setup & Start

### 1. Repository klonen
```powershell
git clone https://github.com/Martin-Frei/SUSI.git
cd SUSI
```

### 2. venv erstellen und aktivieren
```powershell
python -m venv susi_env
susi_env\Scripts\activate
pip install -r requirements.txt
```

### 3. Ollama Modelle laden
```powershell
ollama pull qwen2.5-coder:7b
ollama pull llama3.1:8b
ollama pull bge-m3
```

### 4. Docs indexieren
```powershell
python rag/ingest.py
```

### 5. SUSI starten
```powershell
python manage.py runserver
```

---

## Projektstruktur

```
SUSI/
├── docs/                        ← SUSIpedia Wissensbasis
│   ├── susi/                    ← SUSI-Eigendokumentation
│   ├── coding/                  ← GMM, StockPredict, HouseOfStacks, Portfolio
│   ├── lernen/                  ← AI, ML, RAG, Python, JS, DevOps
│   ├── projekte/                ← Projektdokumentation, Roadmaps
│   ├── job/                     ← Bewerbungen, CV, LinkedIn
│   ├── martin/                  ← Persönliches Profil
│   ├── technik/                 ← Hardware, Tools, RAG-Einstellungen
│   ├── wissen/                  ← Britannica Wissensbasis (221+ Artikel)
│   ├── familie/                 ← Familiäre Kontexte
│   └── hobbys/                  ← Interessen
├── rag/
│   ├── query.py                 ← Pipeline-Kern (~280 Zeilen, refactored)
│   ├── config.py                ← YAML-Loading + statische Konstanten
│   ├── keywords.py              ← Keyword-Extraktion
│   ├── llm_client.py            ← detect_language, rewrite_query, create_summary
│   ├── utils.py                 ← Hilfsfunktionen
│   ├── debug.py                 ← Logger, Timer, TimingCollector
│   ├── router.py                ← Retrieval-getriebener Profil-Router
│   ├── agent_datum.py           ← Tool Use: deterministisch Datum/Laufzeit
│   ├── agent_pedia.py           ← Wikipedia-Integration
│   ├── agent_britannica.py      ← On-demand Britannica-Fallback
│   ├── ingest.py                ← Markdown → ChromaDB (MD5-Hash-Upsert)
│   └── susi_config.yaml         ← Single Source of Truth
├── core/                        ← Django App (Views, Models, Templates)
│   └── models.py                ← Chat, Message, QueueItem
├── tools/
│   ├── evaluation/              ← RAG Evaluation Framework
│   │   ├── grid_run.py          ← Eval-Runner
│   │   ├── auto_scorer.py       ← Diagnostic Scale 0–6 + ValueCheck
│   │   ├── valuecheck.py        ← Deterministische Zahlen/Datums-Prüfung
│   │   ├── referenz_loader.py   ← Dynamische Referenz-Templates
│   │   ├── ragas_scorer.py      ← RAGAS für Grauzonen
│   │   ├── analyse_csv.py       ← Router-Accuracy + Cross-Tab
│   │   └── chunk_audit.py       ← ChromaDB-Diagnose (Übergroße Chunks)
│   └── britannica_index.json    ← Artikel-Tracking (Delta-Updates)
├── A_documentation/
│   └── susi_wissenschaft/       ← 8-teilige wissenschaftliche Doku (öffentlich)
└── manage.py
```

---

## Roadmap

### Stufe 1 – Lokaler RAG-Assistent ✅
Ollama + ChromaDB + LangChain + Django/HTMX. Vollständiges Eval-Framework. Query Rewriting. Multilingualer Reranker.

### Stufe 1.1 – Retrieval-getriebener Router ✅
Dynamische Profil-Auswahl aus SUSIpedia-Ordnerstruktur. Kein Keyword-Matching.

### Stufe 1.2 – Tool Use / Agenten ✅
Deterministischer Guard vor dem LLM. Kalenderfragen in 0.001s statt 8s. Modulare Architektur: `agent_datum`, `agent_pedia`, `agent_britannica`.

### Stufe 1.3 – Wissenserweiterung ✅ (Basis)
Britannica API Integration mit 221+ Artikeln in `docs/wissen/`. Wikipedia-Fallback via `agent_pedia`. On-demand-Fetch bei niedrigem Reranker-Score. Ausbau läuft.

### Stufe 1.4 – Speed & Modularisierung ✅
Pipeline-Latenz halbiert (26s → ~12s). `query.py` in fünf fokussierte Module aufgeteilt. Debug-System mit Phasen-Timing. Reranker-Performance 120s → 3–5s.

### Stufe 2 – Physischer Assistent (geplant)
Raspberry Pi 5 als Sensor-/Voice-Gateway · Whisper STT · Hailo AI HAT+ für Vision · Home Assistant Integration.

### Stufe 3 – Persönlicher Lebensassistent (Vision)
Vollständiges Second Brain · LangChain Agents · eigenständiges Handeln.

**Hardware-Roadmap:** Dual RTX 3090 Build (2× 24 GB = 48 GB VRAM) auf AM5-Plattform, Herbst 2026. Codename: **David**. Ermöglicht 35B+ Modelle, vLLM, Reranker auf GPU.

---

## Sicherheit & Datenschutz

- Vollständig lokal, keine Cloud-Abhängigkeiten
- Festplatte verschlüsselt via BitLocker
- Keine Telemetrie · einziger externer Call: Britannica API (nur Themennamen, opt-in)
- Lokale Fonts, kein externer Request im Frontend
- Prompt-Injection-Schutz auf der Roadmap (relevant ab externer Dokumenten-Ingestion)

---

## Verwandte Projekte

| Projekt | Beschreibung |
|---|---|
| **StockPredict V2** | LSTM + XGBoost Ensemble für 12 US-Bank-Aktien, deployed auf Railway |
| **Global Market Mood** | Sentiment-Analyse globaler Finanznachrichten (160+ RSS Feeds, 4.000+ Artikel/Stunde) |
| **HouseOfStocks** | FinTech Portfolio-Dashboard mit Django + Supabase |

---

*Entwickler: Martin Freimuth · [github.com/Martin-Frei](https://github.com/Martin-Frei) · [martin-freimuth.dev](https://martin-freimuth.dev) · Stand: August 2026*