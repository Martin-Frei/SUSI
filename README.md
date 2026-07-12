# SUSI — Selbständige und Schlaue Intelligenzbestie

> Vollständig lokaler, DSGVO-konformer KI-Assistent mit RAG-Wissensbasis.  
> Kein einziges Byte verlässt den lokalen Rechner.

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6B35?style=for-the-badge&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logoColor=white)

**97% Antwort-Korrektheit · 5.860 automatisierte Eval-Runs · 0.001s deterministisch statt 8s LLM-Halluzination**

---

## Was ist SUSI?

SUSI ist ein persönlicher KI-Assistent der vollständig lokal läuft — keine Cloud, keine externen APIs, keine Datenweitergabe. Die Wissensbasis heißt **SUSIpedia**: eine wachsende Sammlung von Markdown-Dateien mit Projekten, Lernnotizen und persönlichem Kontext.

Das System kombiniert **Retrieval-Augmented Generation (RAG)** mit lokalen LLMs über Ollama. SUSIpedia ist der eigentliche Kern — SUSI ist modell-agnostisch und funktioniert mit jedem Ollama-Modell.

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
Spracherkennung (ISO 639-1, LLM-Call, ~0.1s)
     ↓
agent_datum Guard ──── Kalenderfrage? ────► Python datetime → Antwort (~0.001s)
     │ nein
     ▼
Query Rewriting (Coreference-Auflösung, letzte 2 Q/A)
     ↓
ChromaDB Retrieval (bge-m3, top-k Chunks)
     ↓
bge-reranker-v2-m3 (Top-n behalten)
     ↓
agent_datum Zweig 2 ── Laufzeitfrage? ───► Datum aus Chunk, Python rechnet
     │ nein                                 Fakt ins Prompt injiziert
     ▼
Retrieval-getriebener Router
     ↓
LLM generiert Antwort (qwen2.5-coder:7b / llama3.1:8b / qwen2.5:7b)
     ↓
Frontend (Django + HTMX, tok/s + Quelldateien)
```

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

---

## Evaluation Framework

SUSI hat ein vollständiges RAG-Evaluierungs-Framework unter `tools/evaluation/`:

**Vier-Stufen-Pipeline:** Auto-Scorer (Diagnostic Scale 0–5) → ValueCheck (deterministische Zahlen/Datums-Prüfung) → RAGAS (Grauzonen) → Haiku-Judge (verbleibende Unklarheiten)

### Ergebnisse

| Lauf | Fragen | Runs | Ergebnis | Highlight |
|---|---|---|---|---|
| Lauf D | 293 | 800 | **97.1% Korrektheit** | bge-reranker-v2-m3 vs. amberoad: 97% vs. 59% |
| Lauf E | 293 | 586 | 96.9% (qwen3:8b) | Thinking=on vs. off: 0.011 Punkte Unterschied |
| Lauf F | 293 | 293 | Bug gefunden | Doppeltes Rewriting kostete 16 Prozentpunkte |

**Wichtigste Erkenntnis:** Die größte Qualitätsverbesserung kam nicht durch Modell-Tuning sondern durch bessere Dokumentstruktur — Retrieval Hit Rate von **36% auf 91%** allein durch SUSIpedia-Formatierung und Chunk-Size-Erhöhung.

---

## Tech Stack

| Komponente | Technologie |
|---|---|
| Backend | Django |
| Frontend | HTMX |
| LLM primär | Ollama – `qwen2.5-coder:7b` |
| LLM sekundär | Ollama – `llama3.1:8b`, `qwen2.5:7b` |
| LLM optional | `qwen3:8b`, `qwen3:14b` (Thinking-Modus) |
| Embeddings | `BAAI/bge-m3` |
| Reranker | `BAAI/bge-reranker-v2-m3` |
| Vector Store | ChromaDB (lokal) |
| Orchestrierung | LangChain |
| Wissensbasis | SUSIpedia – Markdown-Dateien, 617+ Chunks |
| Konfiguration | `susi_config.yaml` – Single Source of Truth |
| Tool Use | `agent_datum.py` – deterministisch, 0.001s |

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
❌   Isolation Forest => contamination=0.05, n_estimators=100
✅  Der Isolation Forest verwendet eine Contamination von 0.05
    was einer erwarteten Anomalierate von 5 Prozent entspricht.
```

---

## Setup & Start

### 1. Repository klonen
```powershell
git clone https://github.com/Martin-Frei/SUSI_neu.git
cd SUSI_neu
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
│   ├── familie/                 ← Familiäre Kontexte
│   └── hobbys/                  ← Interessen
│   ├── wissen/                  ← Britannica Wissensbasis (in Aufbau)
├── rag/
│   ├── query.py                 ← Produktions-Pipeline
│   ├── router.py                ← Retrieval-getriebener Profil-Router
│   ├── agent_datum.py           ← Tool Use: deterministisch Datum/Laufzeit
│   ├── ingest.py                ← Markdown → ChromaDB (MD5-Hash-Upsert)
│   └── susi_config.yaml         ← Single Source of Truth
├── core/                        ← Django App (Views, URLs, Templates)
├── tools/
│   └── evaluation/              ← RAG Evaluation Framework
│       ├── grid_run.py          ← Eval-Runner
│       ├── auto_scorer.py       ← Diagnostic Scale 0–5 + ValueCheck
│       ├── valuecheck.py        ← Deterministische Zahlen/Datums-Prüfung
│       ├── referenz_loader.py   ← Dynamische Referenz-Templates
│       ├── ragas_scorer.py      ← RAGAS für Grauzonen
│       └── analyse_csv.py       ← Router-Accuracy + Cross-Tab
└── manage.py
```

---

## Roadmap

### Stufe 1 – Lokaler RAG-Assistent ✅
Ollama + ChromaDB + LangChain + Django/HTMX. Vollständiges Eval-Framework. Query Rewriting. Multilingualer Reranker.

### Stufe 1.1 – Retrieval-getriebener Router ✅
Dynamische Profil-Auswahl aus SUSIpedia-Ordnerstruktur. Kein Keyword-Matching.

### Stufe 1.2 – Tool Use / agent_datum ✅
Deterministischer Guard vor dem LLM. Kalenderfragen in 0.001s statt 8s. Zwei Zweige: direkte Rechnung + Datum aus Chunk.

### Stufe 1.3 – Wissenserweiterung (aktiv)
Britannica API Integration. Neues Profil `wissen`. agent_britannica als zweites Werkzeug.

### Stufe 2 – Physischer Assistent (geplant)
Arduino + Raspberry Pi · Sensoren · Smart Home via Home Assistant.

### Stufe 3 – Persönlicher Lebensassistent (Vision)
Vollständiges Second Brain · LangChain Agents · eigenständiges Handeln.

---

## Sicherheit & Datenschutz

- Vollständig lokal, keine Cloud-Abhängigkeiten
- Festplatte verschlüsselt via BitLocker
- Keine Telemetrie, keine externen API-Calls
- Lokale Fonts, kein externer Request

---

## Verwandte Projekte

| Projekt | Beschreibung |
|---|---|
| **StockPredict V2** | LSTM + XGBoost Aktienvorhersage, deployed auf Railway |
| **Global Market Mood** | Sentiment-Analyse globaler Finanznachrichten (160+ RSS Feeds, 4.000+ Artikel/Stunde) |
| **HouseOfStocks** | FinTech Portfolio-Dashboard mit Django + Supabase |

---

*Entwickler: Martin Freimuth · [github.com/Martin-Frei](https://github.com/Martin-Frei) · [martin-freimuth.dev](https://martin-freimuth.dev) · Stand: Juli 2026*