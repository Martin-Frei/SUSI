# SUSI — Selbständige und Schlaue Intelligenzbestie
### (Independent and Clever Intelligence Beast)

> Fully local, privacy-compliant AI assistant with a RAG knowledge base.  
> Personal data never leaves the local machine.

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6B35?style=for-the-badge&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logoColor=white)

**97% answer correctness · 5,860 automated eval runs · 0.001s deterministic instead of 8s LLM hallucination**

---

## What is SUSI?

SUSI is a personal AI assistant that runs entirely locally — no cloud, no data sharing. The knowledge base is called **SUSIpedia**: a growing collection of Markdown files containing projects, learning notes, and personal context.

The system combines **Retrieval-Augmented Generation (RAG)** with local LLMs via Ollama. SUSIpedia is the true core of the system — SUSI is model-agnostic and works with any Ollama model.

SUSI grew out of a simple conviction: a personal assistant that knows everything about me doesn't belong in the cloud. So everything runs locally — and the interesting engineering question becomes how much quality you can squeeze out of 7B models on consumer hardware. Answer: 97%.

**One exception:** the Britannica integration (Stage 1.3) calls a curated encyclopedia API — outgoing requests contain only the topic name, never personal data. The retrieved knowledge is indexed locally.

---

## SUSI in Action

![SUSI Chat Screenshot](screenshots/SUSI_Chat.jpg)

Three questions, three different mechanisms:

| Question | Mechanism | Time | Answer |
|---|---|---|---|
| "How old is SUSI?" | Branch 2: date extracted from chunk, Python calculates | 6.69s | SUSI is 3 months (114 days) old ✅ |
| "How many days until November 29th?" | Branch 1: Python datetime directly | **0.001s** | 140 days ✅ |
| "How many days until Martin's birthday?" | Branch 1: birthday anchor, Python | **0.001s** | 140 days ✅ |

**Why this matters:** date questions are no longer left to the LLM — LLMs structurally hallucinate on arithmetic. Python's datetime is deterministic. `agent_datum` intercepts these questions before the LLM gets a chance to answer them wrong.

---

## Core Architecture

```
Question comes in
     ↓
Language detection (ISO 639-1, LLM call, ~0.1s)
     ↓
agent_datum guard ──── calendar question? ────► Python datetime → answer (~0.001s)
     │ no
     ▼
Query rewriting (coreference resolution, last 2 Q&A pairs)
     ↓
ChromaDB retrieval (bge-m3, top-k chunks)
     ↓
bge-reranker-v2-m3 (keep top-n)
     ↓
agent_datum branch 2 ── duration question? ───► date extracted from chunk,
     │ no                                        Python calculates,
     ▼                                           fact injected into prompt
Retrieval-driven router
     ↓
LLM generates answer (qwen2.5-coder:7b / llama3.1:8b / qwen2.5:7b)
     ↓
Frontend (Django + HTMX, tok/s + source files)
```

---

## Retrieval-Driven Router

The core architectural idea behind SUSI: not keyword matching, but the **SUSIpedia folder structure itself** determines which LLM and parameters are used.

```python
# Example voting (reranker-score-weighted):
# Chunk 1 (score=0.92) from docs/coding/  → projekte: 0.92
# Chunk 2 (score=0.71) from docs/lernen/  → lernen:   0.71
# Chunk 3 (score=0.68) from docs/lernen/  → lernen:  +0.68 = 1.39  ← winner
```

| Profile | LLM | Use case |
|---|---|---|
| susi | qwen2.5-coder:7b | SUSI self-knowledge |
| projekte | qwen2.5-coder:7b | Code projects |
| lernen | llama3.1:8b | Learning material, concepts |
| persoenlich | qwen2.5:7b | Personal, job |
| technik | qwen2.5-coder:7b | Hardware, tools |
| wissen | planned | Britannica knowledge base |

---

## Evaluation Framework

SUSI has a complete RAG evaluation framework under `tools/evaluation/`:

**Four-stage pipeline:** Auto-Scorer (Diagnostic Scale 0–5) → ValueCheck (deterministic number/date verification) → RAGAS (grey-zone cases) → Haiku Judge (remaining ambiguity)

### Results

| Run | Questions | Runs | Result | Highlight |
|---|---|---|---|---|
| Run D | 293 | 800 | **97.1% correctness** | bge-reranker-v2-m3 vs. amberoad: 97% vs. 59% |
| Run E | 293 | 586 | 96.9% (qwen3:8b) | Thinking on vs. off: 0.011 point difference |
| Run F | 293 | 293 | Bug found | Double rewriting cost 16 percentage points |

**Key insight:** the biggest quality improvement came not from model tuning but from better document structure — retrieval hit rate improved from **36% to 91%** through SUSIpedia formatting and chunk-size increase alone.

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Django |
| Frontend | HTMX |
| LLM (primary) | Ollama – `qwen2.5-coder:7b` |
| LLM (secondary) | Ollama – `llama3.1:8b`, `qwen2.5:7b` |
| LLM (optional) | `qwen3:8b`, `qwen3:14b` (thinking mode) |
| Embeddings | `BAAI/bge-m3` |
| Reranker | `BAAI/bge-reranker-v2-m3` |
| Vector store | ChromaDB (local) |
| Orchestration | LangChain |
| Knowledge base | SUSIpedia – Markdown files, 617+ chunks |
| Configuration | `susi_config.yaml` – single source of truth |
| Tool use | `agent_datum.py` – deterministic, 0.001s |
| Performance | `keep_alive: 300` — models stay in VRAM for 5 min, no 40s cold start |

**Hardware:** AMD Ryzen 9 5900X · 32 GB RAM · RTX 4070 12 GB VRAM

---

## SUSIpedia — Philosophy

```
One .md file      = One clearly defined topic
One ## section    = Becomes its own ChromaDB chunk
Max 3 levels      = Life area → Project → Aspect
```

**Key rule:** always use complete sentences instead of compact lists.
The first sentence of every `##` section must contain the full context
so the chunk is understandable without the rest of the document.

```
❌  contamination=0.05, n_estimators=100
✅  The Isolation Forest uses a contamination of 0.05, which corresponds
    to an expected anomaly rate of 5 percent.
```

---

## Setup & Start

### 1. Clone the repository
```powershell
git clone https://github.com/Martin-Frei/SUSI.git
cd SUSI
```

### 2. Create and activate the virtual environment
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

### 4. Index the docs
```powershell
python rag/ingest.py
```

### 5. Start SUSI
```powershell
python manage.py runserver
```

---

## Project Structure

```
SUSI/
├── docs/                        ← SUSIpedia knowledge base
│   ├── susi/                    ← SUSI self-documentation
│   ├── coding/                  ← GMM, StockPredict, HouseOfStacks, Portfolio
│   ├── lernen/                  ← AI, ML, RAG, Python, JS, DevOps
│   ├── projekte/                ← Project documentation, roadmaps
│   ├── job/                     ← Job applications, CV, LinkedIn
│   ├── martin/                  ← Personal profile
│   ├── technik/                 ← Hardware, tools, RAG settings
│   ├── wissen/                  ← Britannica knowledge base (in progress)
│   ├── familie/                 ← Family context
│   └── hobbys/                  ← Interests
├── rag/
│   ├── query.py                 ← Production pipeline
│   ├── router.py                ← Retrieval-driven profile router
│   ├── agent_datum.py           ← Tool use: deterministic date/duration
│   ├── ingest.py                ← Markdown → ChromaDB (MD5-hash upsert)
│   └── susi_config.yaml         ← Single source of truth
├── core/                        ← Django app (views, URLs, templates)
├── tools/
│   └── evaluation/              ← RAG evaluation framework
│       ├── grid_run.py          ← Eval runner
│       ├── auto_scorer.py       ← Diagnostic Scale 0–5 + ValueCheck
│       ├── valuecheck.py        ← Deterministic number/date verification
│       ├── referenz_loader.py   ← Dynamic reference templates
│       ├── ragas_scorer.py      ← RAGAS for grey-zone cases
│       └── analyse_csv.py       ← Router accuracy + cross-tab
└── manage.py
```

---

## Roadmap

### Stage 1 – Local RAG Assistant ✅
Ollama + ChromaDB + LangChain + Django/HTMX. Complete evaluation framework. Query rewriting. Multilingual reranker.

### Stage 1.1 – Retrieval-Driven Router ✅
Dynamic profile selection from the SUSIpedia folder structure. No keyword matching.

### Stage 1.2 – Tool Use / agent_datum ✅
Deterministic guard in front of the LLM. Calendar questions in 0.001s instead of 8s. Two branches: direct calculation + date extracted from chunk.

### Stage 1.3 – Knowledge Expansion (active)
Britannica API integration. New `wissen` profile. `agent_britannica` as the second tool.

### Stage 2 – Physical Assistant (planned)
Arduino + Raspberry Pi · sensors · smart home via Home Assistant.

### Stage 3 – Personal Life Assistant (vision)
Complete second brain · LangChain agents · autonomous action.

---

## Security & Privacy

- Runs fully locally, no cloud dependencies
- Hard drive encrypted via BitLocker
- No telemetry · the only external call is the Britannica API (topic names only, opt-in)
- Local fonts, no external requests in the frontend

---

## Related Projects

| Project | Description |
|---|---|
| **StockPredict V2** | LSTM + XGBoost ensemble for 12 US bank stocks, deployed on Railway |
| **Global Market Mood** | Sentiment analysis of global financial news (160+ RSS feeds, 4,000+ articles/hour) |
| **HouseOfStocks** | FinTech portfolio dashboard with Django + Supabase |

---

*Developer: Martin Freimuth · [github.com/Martin-Frei](https://github.com/Martin-Frei) · [martin-freimuth.dev](https://martin-freimuth.dev) · As of: July 2026*