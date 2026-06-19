# SUSI – Selbständige und Schlaue Intelligenzbestie

> Vollständig lokaler, DSGVO-konformer KI-Assistent mit RAG-Wissensbasis.  
> Kein einziges Byte verlässt den lokalen Rechner.

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6B35?style=for-the-badge&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logoColor=white)

---

## Was ist SUSI?

SUSI ist ein persönlicher KI-Assistent der komplett lokal läuft — keine Cloud, keine externen APIs, keine Datenweitergabe. Die Wissensbasis heißt **SUSIpedia**: eine wachsende Sammlung von Markdown-Dateien die Martins Projekte, Lernnotizen, Code-Kontext und persönliche Informationen enthält.

Das System kombiniert **Retrieval-Augmented Generation (RAG)** mit lokalen LLMs über Ollama. SUSIpedia ist der eigentliche Kern — das System ist modell-agnostisch und funktioniert mit jedem Ollama-Modell.

---

## Tech Stack

| Komponente | Technologie |
|---|---|
| Backend | Django |
| Frontend | HTMX |
| LLM (primär) | Ollama – `qwen2.5-coder:7b` |
| LLM (sekundär) | Ollama – `llama3.1:8b` |
| Embeddings | `BAAI/bge-m3` |
| Reranker | `BAAI/bge-reranker-v2-m3` |
| Vector Store | ChromaDB (lokal) |
| Orchestrierung | LangChain (Retrieval + Chunking) |
| Wissensbasis | SUSIpedia – 41+ Markdown Files, 617 Chunks |
| Konfiguration | `susi_config.yaml` – Single Source of Truth |

**Hardware:** AMD Ryzen 9 5900X · 32 GB RAM · RTX 4070 12 GB VRAM

---

## Projektstruktur

```
SUSI/
├── docs/                        ← SUSIpedia Wissensbasis
│   ├── susi/                    ← SUSI selbst (Architektur, Vision, Evaluation)
│   ├── coding/                  ← Projekte: GMM, StockPredict, HouseOfStocks, Portfolio
│   ├── lernen/                  ← AI, ML, RAG, Python, HTMX, DevOps, ...
│   ├── projekte/                ← Projektdokumentation, Roadmaps
│   ├── job/                     ← Jobsuche, Bewerbungen, CV, LinkedIn
│   ├── martin/                  ← Persönliches Profil, Werte, Ziele
│   ├── technik/                 ← Hardware, Tools, Setup
│   ├── familie/                 ← Familiäre Kontexte
│   └── hobbys/                  ← Interessen, Freizeit
├── rag/
│   ├── ingest.py                ← Markdown → ChromaDB (Upsert mit MD5-Hash)
│   ├── query.py                 ← Frage → Retrieval → Reranker → LLM → Antwort
│   └── susi_config.yaml         ← Alle Parameter zentral
├── core/                        ← Django App (Views, URLs, Templates)
├── susi_project/                ← Django Settings
├── tools/
│   └── evaluation/              ← RAG Evaluation Framework
│       ├── grid_run.py          ← Grid Search über alle Parameterkombinationen
│       ├── evaluator.py         ← BERTScore + ROUGE-L Metriken
│       ├── auto_scorer.py       ← Automatische Bewertung (0–3 Skala)
│       ├── retrieval_check.py   ← Hit Rate Messung
│       ├── eval_meta.py         ← Metadaten pro Run
│       ├── analyse_csv.py       ← Ergebnisanalyse
│       └── results/             ← CSV Ergebnisse
├── chroma_db/                   ← Lokale Vektordatenbank
└── manage.py
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

### Alles neu indexieren (Reset)
```powershell
Remove-Item -Recurse -Force chroma_db\
python rag/ingest.py
```

---

## Wie die RAG-Pipeline funktioniert

```
Frage eingeben
     ↓
Frage → Embedding (bge-m3)
     ↓
ChromaDB: Top-k ähnliche Chunks aus SUSIpedia (similarity oder MMR)
     ↓
bge-reranker-v2-m3: Chunks neu sortieren → Top-n behalten
     ↓
Chunks + Frage + System Prompt → Ollama LLM (qwen2.5-coder:7b)
     ↓
Antwort + Quellen + tok/s Metriken → Django/HTMX Frontend
```

---

## SUSIpedia – Philosophie

```
Eine .md Datei    = Ein klar abgegrenztes Thema
Ein ## Abschnitt  = Wird zu eigenem ChromaDB-Chunk
Max 3 Ebenen      = Lebensbereich → Projekt → Aspekt
```

**Wichtigste Regel:** Immer vollständige Sätze statt kompakter Listen.  
Kompakte Listen retrieven schlecht — der erste Satz jedes `##` Abschnitts  
muss den vollständigen Kontext enthalten damit der Chunk ohne das restliche  
Dokument verständlich ist.

```
❌  contamination=0.05, n_estimators=100
✅  Der Isolation Forest verwendet eine Contamination von 0.05
    was einer erwarteten Anomalierate von 5 Prozent entspricht.
```

---

## Evaluation Framework

SUSI hat ein vollständiges RAG-Evaluierungs-Framework unter `tools/evaluation/`:

```powershell
# Smoke Test (4 Fragen, schnell)
python tools/evaluation/grid_run.py --mode smoke --config tools/evaluation/eval_config_lauf_C.yaml

# Full Run (293 Fragen, über Nacht)
python tools/evaluation/grid_run.py --mode full --config tools/evaluation/eval_config_lauf_C.yaml

# Dry Run (nur Kombinationen anzeigen)
python tools/evaluation/grid_run.py --dry-run --mode full --config tools/evaluation/eval_config_lauf_C.yaml
```

### Ergebnisse Lauf C (Juni 2026)

**5.860 automatisierte Runs · 293 Fragen · 20 Parameterkombinationen**

| Konfiguration | Ø Score | Korrekt |
|---|---|---|
| k=3, ohne Reranker | 2.97 / 3.0 | 98% |
| k=7, mit Reranker | 3.01 / 3.0 | **100%** |
| qwen2.5-coder:7b | 3.02 / 3.0 | 100% |
| llama3.1:8b | 2.98 / 3.0 | 99% |

**Reranker-Vergleich (Smoke Test):**

| Reranker | Mit Reranker (k≥5) |
|---|---|
| amberoad/bert-multilingual | 59% ❌ |
| **BAAI/bge-reranker-v2-m3** | **97%** ✅ |

**Wichtigste Erkenntnis:** Die größte Qualitätsverbesserung kam nicht durch Modell-Tuning  
sondern durch bessere Dokumentstruktur — Hit Rate von 36% auf 91% allein durch  
SUSIpedia-Formatierung und Chunk-Size-Erhöhung (300 → 1000 Tokens).

---

## Roadmap

### Stufe 1 – Coding Assistent (aktiv ✅)
Lokaler RAG mit Ollama + ChromaDB + LangChain + Django/HTMX.  
Vollständiges Evaluation Framework. Multilingualer Reranker.

### Stufe 2 – Retrieval-getriebener Router (in Entwicklung 🔧)
Dynamische Profil-Auswahl basierend auf den retrievten SUSIpedia-Ordnern.  
Die Wissensbasis-Struktur bestimmt LLM, top_k und Parameter — kein Keyword-Matching.

### Stufe 3 – Physischer Assistent (geplant)
Arduino + Raspberry Pi · Sensoren · Smart Home via Home Assistant.

### Stufe 4 – Persönlicher Lebensassistent (Vision)
Vollständiges Second Brain · LangChain Agents · eigenständiges Handeln.

---

## Sicherheit & Datenschutz

- Läuft vollständig lokal, keine Cloud-Abhängigkeiten
- Festplatte verschlüsselt via BitLocker
- Keine Telemetrie, keine externen API-Calls

---

## Verwandte Projekte

| Projekt | Beschreibung |
|---|---|
| **StockPredict V2** | LSTM + XGBoost Aktienvorhersage, deployed auf Railway |
| **Global Market Mood (GMM)** | Sentiment-Analyse globaler Finanznachrichten (160+ RSS Feeds) |
| **HouseOfStocks** | Portfolio-Dashboard mit Django + Supabase |
| **SAP Fraud Detection** | Anomalie-Erkennung für SAP Sales Orders + Email Verification |

---

## 🇬🇧 English Summary

SUSI is a fully local RAG assistant — no cloud, no external APIs, no data leaving the machine.

**Stack:** Python · Django · HTMX · ChromaDB · Ollama · bge-m3 · bge-reranker-v2-m3 · qwen2.5-coder:7b

**Key results from Evaluation Run C (5,860 automated runs):**
- 98–100% answer correctness across 293 questions
- Biggest improvement: document quality (Hit Rate 36% → 91%), not model tuning
- Wrong reranker actively harmful: amberoad 59% vs bge-reranker-v2-m3 97%

**Next:** Retrieval-driven router — the knowledge base folder structure determines which LLM and parameters to use. No keyword matching, no extra model call.

---

*Entwickler: Martin Freimuth · [github.com/Martin-Frei](https://github.com/Martin-Frei) · [martin-freimuth.dev](https://martin-freimuth.dev) · Stand: Juni 2026*