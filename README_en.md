# SUSI – Selbständige und Schlaue Intelligenzbestie

> Fully local, privacy-compliant AI assistant with a RAG knowledge base.  
> Not a single byte leaves the local machine.

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6B35?style=for-the-badge&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logoColor=white)

---

## What is SUSI?

SUSI is a personal AI assistant that runs entirely locally – no cloud, no external APIs, no data sharing. The knowledge base is called **SUSIpedia**: a growing collection of Markdown files containing Martin's projects, learning notes, code context and personal information.

The system combines **Retrieval-Augmented Generation (RAG)** with local LLMs via Ollama. SUSIpedia is the true core of the system – SUSI is model-agnostic and works with any Ollama model.

---

## Query Rewriting in Action

![SUSI Chat](screenshots/SUSI_Chat.jpg)

The screenshot shows the evolution of answer quality through query rewriting and SUSIpedia optimization:

| Question | Result | Tokens |
|---|---|---|
| "Hello SUSI I am Martin Where do I live??" | ❌ Wrong — refers to apartment search category | 76 |
| "Where does Martin Freimuth live??" | ✅ Correct — direct 3rd person | 13 |
| "I am Martin. Where do I live" | ✅ Correct — via `ich_bin_martin.md` | 23 |
| "I am Martin where do I live ??" | ✅ Correct — Query Rewriting + Reranker | 25 |

**Key insight:** Query rewriting automatically converts first-person questions into optimal search queries. Shorter answers, higher precision, correct profile selection by the router.

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Django |
| Frontend | HTMX |
| LLM (primary) | Ollama – `qwen2.5-coder:7b` |
| LLM (secondary) | Ollama – `llama3.1:8b` |
| Embeddings | `BAAI/bge-m3` |
| Reranker | `BAAI/bge-reranker-v2-m3` |
| Vector Store | ChromaDB (local) |
| Orchestration | LangChain |
| Knowledge Base | SUSIpedia – 41+ Markdown files, 617 chunks |
| Configuration | `susi_config.yaml` – Single Source of Truth |

**Hardware:** AMD Ryzen 9 5900X · 32 GB RAM · RTX 4070 12 GB VRAM

---

## Project Structure

```
SUSI/
├── docs/                        ← SUSIpedia knowledge base
│   ├── susi/                    ← SUSI itself (architecture, vision, evaluation)
│   ├── coding/                  ← Projects: GMM, StockPredict, HouseOfStocks, Portfolio
│   ├── lernen/                  ← AI, ML, RAG, Python, HTMX, DevOps, ...
│   ├── projekte/                ← Project documentation, roadmaps
│   ├── job/                     ← Job search, applications, CV, LinkedIn
│   ├── martin/                  ← Personal profile, values, goals
│   ├── technik/                 ← Hardware, tools, setup
│   ├── familie/                 ← Family context
│   └── hobbys/                  ← Interests, leisure
├── rag/
│   ├── ingest.py                ← Markdown → ChromaDB (upsert with MD5 hash)
│   ├── query.py                 ← Query Rewriting → Retrieval → Reranker → Router → LLM → Answer
│   ├── router.py                ← Retrieval-driven profile router
│   └── susi_config.yaml         ← All parameters centrally (incl. router profiles)
├── core/                        ← Django app (views, URLs, templates)
├── susi_project/                ← Django settings
├── tools/
│   └── evaluation/              ← RAG evaluation framework
│       ├── grid_run.py          ← Grid search over all parameter combinations
│       ├── evaluator.py         ← BERTScore + ROUGE-L metrics
│       ├── auto_scorer.py       ← Automated scoring (0–3 scale)
│       ├── retrieval_check.py   ← Hit rate measurement
│       ├── eval_meta.py         ← Metadata per run
│       ├── analyse_csv.py       ← Results analysis
│       └── results/             ← CSV results
├── chroma_db/                   ← Local vector database
└── manage.py
```

---

## Setup & Start

### 1. Clone repository
```powershell
git clone https://github.com/Martin-Frei/SUSI_neu.git
cd SUSI_neu
```

### 2. Create and activate venv
```powershell
python -m venv susi_env
susi_env\Scripts\activate
pip install -r requirements.txt
```

### 3. Pull Ollama models
```powershell
ollama pull qwen2.5-coder:7b
ollama pull llama3.1:8b
ollama pull bge-m3
```

### 4. Index docs
```powershell
python rag/ingest.py
```

### 5. Start SUSI
```powershell
python manage.py runserver
```

### Full reindex (reset)
```powershell
Remove-Item -Recurse -Force chroma_db\
python rag/ingest.py
```

---

## How the RAG Pipeline Works

```
Enter question
     ↓
Query Rewriting — LLM rewrites question into optimal search query
("I am Martin. Where do I live?" → "Where does Martin Freimuth live?")
     ↓
Embedding (bge-m3) → ChromaDB: Top-k similar chunks (similarity or MMR)
     ↓
bge-reranker-v2-m3: Re-rank chunks → keep Top-n
     ↓
Router: folder path of Top chunks determines profile (LLM + parameters)
     ↓
Chunks + original question + system prompt → Ollama LLM
     ↓
Answer + sources + tok/s metrics → Django/HTMX frontend
```

---

## Retrieval-Driven Router

The key architectural innovation: not keyword matching but the **SUSIpedia folder structure itself** determines which LLM and parameters to use for each query.

```python
# Example voting:
# Chunk 1 (score=0.92) from coding/  → projekte: 0.92
# Chunk 2 (score=0.71) from lernen/  → lernen:   0.71
# Chunk 3 (score=0.68) from lernen/  → lernen:  +0.68 = 1.39  ← winner
```

| Profile | LLM | top_k | Use case |
|---|---|---|---|
| susi | qwen2.5-coder:7b | 7 | SUSI self-knowledge |
| projekte | qwen2.5-coder:7b | 7 | Code projects |
| lernen | llama3.1:8b | 9 | Learning material, concepts |
| persoenlich | qwen2.5-coder:7b | 5 | Personal, job |
| technik | qwen2.5-coder:7b | 5 | Hardware, tools |

Profiles are defined in `susi_config.yaml` and already include a `thinking` flag for upcoming qwen3 models — no code changes needed when switching models.

---

## SUSIpedia – Philosophy

```
One .md file      = One clearly defined topic
One ## section    = Becomes its own ChromaDB chunk
Max 3 levels      = Life area → Project → Aspect
```

**Key rule:** Always use complete sentences instead of compact lists.  
Compact lists retrieve poorly from vector search — the first sentence of every `##` section  
must contain the full context so the chunk is understandable without the rest of the document.

```
❌  contamination=0.05, n_estimators=100
✅  The Isolation Forest uses a contamination of 0.05 which corresponds
    to an expected anomaly rate of 5 percent.
```

---

## Evaluation Framework

SUSI has a complete RAG evaluation framework under `tools/evaluation/`:

```powershell
# Smoke test (4 questions, fast)
python tools/evaluation/grid_run.py --mode smoke --config tools/evaluation/eval_config_lauf_C.yaml

# Full run (293 questions, overnight)
python tools/evaluation/grid_run.py --mode full --config tools/evaluation/eval_config_lauf_C.yaml

# Dry run (show combinations only)
python tools/evaluation/grid_run.py --dry-run --mode full --config tools/evaluation/eval_config_lauf_C.yaml
```

### Results — Evaluation Run C (June 2026)

**5,860 automated runs · 293 questions · 20 parameter combinations**

| Configuration | Avg Score | Correct |
|---|---|---|
| k=3, no reranker | 2.97 / 3.0 | 98% |
| k=7, with reranker | 3.01 / 3.0 | **100%** |
| qwen2.5-coder:7b | 3.02 / 3.0 | 100% |
| llama3.1:8b | 2.98 / 3.0 | 99% |

**Reranker comparison:**

| Reranker | Correctness |
|---|---|
| amberoad/bert-multilingual | 59% ❌ |
| **BAAI/bge-reranker-v2-m3** | **97%** ✅ |

**Key insight:** The biggest quality improvement came not from model tuning but from better  
document structure — hit rate improved from 36% to 91% through SUSIpedia formatting  
and increasing chunk size from 300 to 1,000 tokens alone.

**Second key insight:** The wrong reranker is actively harmful — amberoad discarded good  
chunks and reduced correctness from 100% to 59%.

---

## Roadmap

### Stage 1 – Coding Assistant (active ✅)
Local RAG with Ollama + ChromaDB + LangChain + Django/HTMX.  
Complete evaluation framework. Multilingual reranker. Query rewriting.

### Stage 2 – Retrieval-Driven Router (complete ✅)
Dynamic profile selection based on retrieved SUSIpedia folders.  
The knowledge base structure determines LLM, top_k and parameters — no keyword matching.  
`thinking` flag already prepared for qwen3 models.

### Stage 3 – Physical Assistant (planned)
Arduino + Raspberry Pi · Sensors · Smart Home via Home Assistant.

### Stage 4 – Personal Life Assistant (vision)
Complete second brain · LangChain agents · autonomous action.

---

## Security & Privacy

- Runs fully locally, no cloud dependencies
- Hard drive encrypted via BitLocker
- No telemetry, no external API calls
- Local fonts (no Google Fonts), zero external requests

---

## Related Projects

| Project | Description |
|---|---|
| **StockPredict V2** | LSTM + XGBoost stock prediction, deployed on Railway |
| **Global Market Mood (GMM)** | Sentiment analysis of global financial news (160+ RSS feeds) |
| **HouseOfStocks** | Portfolio dashboard with Django + Supabase |
| **SAP Fraud Detection** | Anomaly detection for SAP sales orders + email verification |

---

*Developer: Martin Freimuth · [github.com/Martin-Frei](https://github.com/Martin-Frei) · [martin-freimuth.dev](https://martin-freimuth.dev) · As of: June 2026*