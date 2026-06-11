# SUSI – Selbständige und Schlaue Intelligenzbestie

> Fully local, privacy-compliant AI assistant with a RAG knowledge base.  
> Not a single byte leaves the local machine.

---

## What is SUSI?

SUSI is a personal AI assistant that runs entirely locally – no cloud, no external APIs, no data sharing. The knowledge base is called **SUSIpedia**: a growing collection of Markdown files containing Martin's projects, learning notes, code context and personal information.

The system combines **Retrieval-Augmented Generation (RAG)** with local LLMs via Ollama. SUSIpedia is the true core of the system – SUSI is model-agnostic and works with any Ollama model.

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Django |
| Frontend | HTMX |
| LLM | Ollama – `qwen2.5-coder:7b` |
| Embeddings | `nomic-embed-text` (bge-m3 in evaluation) |
| Vector Store | ChromaDB (local) |
| Orchestration | LangChain |
| Knowledge Base | SUSIpedia – Markdown files |

**Hardware:** AMD Ryzen 9 5900X · 32 GB RAM · RTX 3090 24 GB VRAM

---

## Project Structure

```
SUSI/
├── docs/                    ← SUSIpedia knowledge base
│   ├── susi_vision.md       ← Root document
│   ├── coding/              ← Projects: GMM, StockPredict, HouseOfStocks
│   ├── lernen/              ← AI, ML, RAG, Python, HTMX, ...
│   ├── martin/              ← CV, profile, goals
│   ├── job/                 ← Job search, applications, CV
│   ├── projekte/            ← Project documentation
│   ├── hobbys/              ← Dancing, interests
│   ├── familie/             ← Family context
│   └── technik/             ← RAG settings, roadmap
├── rag/
│   ├── ingest.py            ← Markdown → ChromaDB (upsert with hash detection)
│   └── query.py             ← Question → Retrieval → LLM → Answer
├── core/                    ← Django app
├── susi_project/            ← Django settings
├── susi_env/                ← Virtual environment
├── chroma_db/               ← Local vector database
│   └── doc_hashes.json      ← Change detection via MD5
└── manage.py
```

---

## Setup & Start

### 1. Activate venv
```powershell
cd C:\Users\tsinn\VSCode\Repos\SUSI_neu
susi_env\Scripts\activate
```

### 2. Index docs (only needed when files change)
```powershell
python rag/ingest.py
```

### 3. Start SUSI
```powershell
python rag/query.py
```

### Full reindex (reset)
```powershell
Remove-Item -Recurse -Force chroma_db\*
python rag/ingest.py
```

---

## How RAG Works

```
Enter question
     ↓
Question → Embedding (nomic-embed-text)
     ↓
ChromaDB: Top-k most similar chunks from SUSIpedia
     ↓
Chunks + Question + System Prompt → Ollama LLM
     ↓
Return answer
     ↓
worth_saving() → susi_evaluates() → if YES: save to SUSIpedia
     ↓
ingest.py runs automatically in the background
```

---

## SUSIpedia – Philosophy

```
One .md file      = One clearly defined topic
One ## section    = One unit of knowledge with date
Max 3 levels      = Life area → Project → Aspect
```

**Key rule:** Always use complete sentences instead of compact lists.  
Compact lists are poorly retrieved by the vector search.

- ❌ `Champion: xlf_regime = MIXED AND hg-score >= -1.0`  
- ✅ `The Champion Strategy filters where xlf_regime equals MIXED and hg-score is greater than or equal to -1.0.`

---

## Known Issues

- Pydantic V1 warning on Python 3.14 → ignore, works anyway
- k=5 sometimes not enough → increase `k` for complex topics
- Interview-prep chunks can interfere with CV-related queries → metadata filtering planned

---

## Evaluation

SUSI has a complete RAG evaluation framework (`tools/evaluation/`):

- **Test set:** 80–100 questions across 10 categories
- **Grid search:** Embedding model · chunk size · k · temperature · prompt
- **Metrics:** BERTScore + ROUGE-L + automated scorer
- **Result:** From ~29% to ~97% correct answers through systematic optimization

**Best parameter combination:**  
`bge-m3` · Chunk 1000 · Overlap 50 · k=5 · `llama3.1:8b` · Temp 0.0 · `praezise_CoT` prompt

---

## Roadmap

### Stage 1 – Coding Assistant (active ✅)
Local RAG with Ollama + ChromaDB + LangChain + Django/HTMX.

### Stage 2 – Physical Assistant (planned)
Arduino + Raspberry Pi · Sensors · Smart Home via Home Assistant.

### Stage 3 – Personal Life Assistant (vision)
Complete second brain · LangChain agents · autonomous action.

### Edge MCP Server (outlook)
Specialized small models on Raspberry Pis as MCP servers.  
SUSI on the main machine orchestrates these as tools via the MCP protocol.

---

## Security & Privacy

- Runs fully locally, no cloud dependencies
- Hard drive encrypted via BitLocker
- Personal folders additionally via VeraCrypt (planned)
- Planned: access only via facial recognition (Raspberry Pi)

---

## Related Projects

| Project | Description |
|---|---|
| **StockPredict V2** | LSTM + XGBoost stock prediction, deployed on Railway |
| **Global Market Mood (GMM)** | Sentiment analysis of global financial news |
| **HouseOfStocks** | Portfolio dashboard with Django + Supabase |

---

*Developer: Martin Freimuth · [github.com/Martin-Frei](https://github.com/Martin-Frei) · As of: June 2026*