# SUSI — Project Summary
### A Fully Local, GDPR-Compliant AI Assistant
**Author:** Martin Freimuth · **Period:** March – June 2026  
**Stack:** Python · Django · HTMX · LangChain · ChromaDB · Ollama · bge-reranker-v2-m3  
**Repository:** github.com/Martin-Frei/SUSI

---

## What is SUSI?

SUSI (Selbständige und Schlaue Intelligenzbestie — "Independent and Smart Intelligence Beast") is a fully local AI assistant. No cloud services, no external servers, no data transmission. It follows the RAG principle (Retrieval-Augmented Generation) end to end on local hardware.

The central design philosophy:

> *The language model is replaceable. The knowledge base is the actual asset.*

SUSIpedia — the structured Markdown knowledge base — belongs entirely to the user. No model update, no API change, no cloud provider can remove or block access to it.

---

## Chapter 01 — Motivation

SUSI was built to solve three structural weaknesses of commercial AI assistants like Microsoft Copilot or ChatGPT:

**Privacy:** Every input to a cloud-based assistant leaves the local system. Under GDPR, the AI Act, and German trade secret law (GeschGehG), this is a serious legal and operational risk for individuals and companies alike. SUSI processes everything locally — not a single byte leaves the system.

**Unlocking private data:** Personal data (CV, project documentation, learning materials, personal goals) exists scattered across hard drives and note apps. External AI assistants have no access to it. SUSI inverts this: SUSIpedia is a structured knowledge base built from exactly this private data. Questions like *"What are my current career goals?"* or *"What did I learn in the last StockPredict training run?"* are answered from the user's own knowledge store — precisely and without data sharing.

**Learning by building:** Every day spent working on SUSI produces concrete skills: RAG architectures, embedding model evaluation, Django backends, evaluation frameworks, prompt engineering, ChromaDB configuration. Not in theory — in a real, production-running system.

**Reproducibility:** Every architectural decision is documented before implementation. Every evaluation run enters with clear hypotheses. Every discarded idea is recorded with its reason. This discipline makes the system reproducible six months later — by the developer or by anyone else.

---

## Chapter 02 — System Architecture

### The RAG Pipeline

```
User question
       ↓
Query Rewriting resolves first-person references and follow-up questions   [local, LLM]
       ↓
Embedding model converts question into vector                               [local]
       ↓
ChromaDB searches for most similar knowledge chunks                        [local]
       ↓
Reranker (bge-reranker-v2-m3) re-sorts top chunks                         [local, CPU]
       ↓
Router: reranker-weighted voting → selects profile                         [local]
       ↓
Context + original question + system prompt
       ↓
Local LLM generates the answer                                             [local]
```

### Key Stack Decisions

**Django over Flask** — chosen from day one for its ORM, admin interface, template system, and HTMX compatibility. Long-term stability over novelty.

**ChromaDB** — zero-dependency vector store. The database is a local file. Known limitation: no native hybrid search (BM25 + vector). Whether this matters is answered by the evaluation runs.

**Ollama** — local inference server on port 11434. Switching models requires only a config change.

**LangChain** — connects embedding model, ChromaDB, and LLM with minimal boilerplate. Known trade-off: dependency on a fast-moving framework.

**susi_config.yaml** — single source of truth. All parameters (models, chunk sizes, prompts, router profiles) are managed in one file. No hardcoded values anywhere in the code.

### New Pipeline Stages (June 2026)

**Query Rewriting:** Embedding models cannot resolve coreference — "I am Martin. Where do I live?" does not find the right chunk because "I" and "Martin" are not linked in vector space. A lightweight LLM call rewrites the query before retrieval. The rewriter is generic (no overfitting on Martin-specific patterns), can be disabled via config flag, and always falls back to the original question on error.

**Reranker (bge-reranker-v2-m3):** A cross-encoder model re-scores chunks after retrieval and passes only the top_n=3 to the LLM. Runs on CPU — no VRAM consumption. The model selection went through three generations (see Chapter 08).

**Retrieval-Driven Router:** Instead of a fixed parameter set, the router selects the optimal LLM profile based on which SUSIpedia folders the retrieved chunks come from. Five profiles: `susi`, `projekte`, `lernen`, `persoenlich`, `technik` — each with its own LLM, top_k, top_n, and temperature. No extra LLM call needed — the reranker scores are already available.

### Auto-Save Pipeline (deactivated May 2026)

An auto-save pipeline was fully implemented and ran in production. It felt like real AI learning — SUSI learns from conversations. The problem: when the chat model hallucinates, it writes its own errors back into long-term memory undetected. A destructive feedback loop. The pipeline was deactivated. A 3-stage Human-in-the-Loop architecture is planned for Q3 2026.

### How SUSI "Learns" — RAG vs. Gradient Descent

SUSI does not change model weights. Learning happens through structured knowledge management: new knowledge is written as a Markdown file into SUSIpedia, ingested into ChromaDB, and available at the next retrieval. This is transparent, reversible, and fully controllable — the opposite of black-box training.

---

## Chapter 03 — SUSIpedia: The Knowledge Base

### Structure

SUSIpedia is organized by life and work domains:

```
docs/
├── susi/         ← SUSI development documentation
├── coding/       ← Technical projects (GMM, HouseOfStocks, StockPredict, Portfolio)
├── projekte/     ← Project overviews and roadmaps
├── technik/      ← Technical configuration and hardware
├── lernen/       ← Learning materials [not public]
├── martin/       ← Personal data [not public]
├── job/          ← Applications, CV, LinkedIn [not public]
├── familie/      ← Family data [not public]
├── hobbys/       ← Personal interests [not public]
└── persoenlich/  ← Private reflections [not public]
```

**Status June 2026:** 124 files, 617 chunks in ChromaDB. Retrieval hit rate improved from 36% to 91% through document quality improvements alone.

### Formatting Rules — the Foundation of Retrieval Quality

The formatting rules are not optional. They are the reason SUSIpedia works.

**One file — one topic.** A document covering three projects is split into three files. This is a RAG requirement, not a convention.

**Maximum three heading levels.** H1 = file title (once per file). H2 = one concept = one chunk in ChromaDB. H3 = detail to the section above, only when necessary. H4 and deeper are never used.

**Topic-label anchor sentence.** Every H2 section must name its full context in the first sentence. Since ChromaDB stores each chunk without the rest of the document, the chunk must be self-explanatory in isolation. Wrong: *"It consists of three layers."* Correct: *"The StockPredict V2 architecture consists of three layers: DataHandler, MasterEngineer, and Enrichment Pipeline."*

**Prose over bullet lists.** All information is written in complete sentences. Compact lists retrieve poorly because embedding models are optimized for natural language. Technical shorthand produces vectors with little semantic overlap with natural-language queries.

**No Markdown tables.** Tables are shredded during chunking and retrieve poorly. Converted to prose. JSON and YAML code blocks are allowed for structured data (config parameters, API formats) — but every code block must be surrounded by an H2 anchor sentence and explanatory prose.

### The 5 Biggest Quality Problems

**Encoding errors (UTF-8 / Windows):** Umlauts appearing as garbled strings (`ï¿½`) make the affected chunks semantically worthless for the embedding model.

**Bullet lists instead of prose:** Each list item is too short to carry semantic context. bge-m3 cannot find the chunk if the query is phrased differently than the list item.

**Missing topic-label anchor sentences:** A chunk starting without naming its context gets stored without context and can be misassigned to a different project.

**Outdated technical information:** Model names, hardware specs, and config values that are not updated after system changes cause SUSI to state outdated information with full confidence.

**H3 headings and unexplained code blocks:** Produce chunks too small to carry sufficient semantic context.

---

## Chapter 04 — Evaluation

### Why Formal Evaluation?

Quality without measurement is a claim. SUSI was not simply used and declared "good enough." An objective data basis was built early — not intuition.

The evaluation framework answers two fundamental questions:

1. **Retrieval question:** Does the system find the correct knowledge chunk at all?
2. **Generation question:** Does the LLM build the correct answer from the correct chunk?

This separation is crucial. What retrieval does not find, no prompt in the world can repair.

### Metrics

**BERTScore** (introduced 24.05.2026): measures semantic similarity between generated answer and reference answer. Range 0–1, >0.85 is very good. Key additional metric: `max_chunk_bert` — BERTScore of the best retrieved chunk against the reference. The delta `answer_bert - max_chunk_bert` reveals where the problem lies: negative delta = generation problem (chunk had the information, LLM lost it). Positive delta = hallucination risk.

**ROUGE-L** (introduced 26.05.2026): measures the longest common subsequence — lexical, not semantic. The sharper metric for wrong names or wrong model designations. BERTScore would rate "nomic-embed-text" and "bge-m3" as semantically similar because both are embedding models. ROUGE-L detects that the names differ and gives a low score.

### The Auto-Scorer

The auto-scorer (`auto_scorer.py`) reduces the manual scoring workload across hundreds of grid runs. Empirically calibrated from real evaluation data, not theoretically set.

**Score scale (0–3):**

| Score | Meaning |
|-------|---------|
| 0 | Evasive answer — SUSI responds "information not available" |
| 1 | Wrong or incomplete — hallucination, wrong chunk, or missing core statement |
| 2 | Correct from chunk — content matches, from the right document |
| 3 | RAG perfect ✅ — ROUGE-L > 0.10 + BERTScore > 0.65 |

Automation rate: ~86%. Accuracy of automatic decisions: ~88%. The remaining ~14% go through manual Human-in-the-Loop review — this is not a failure of the system, it is the design principle.

### Evaluation Runs — Key Results

| Run | Config | Correctness |
|-----|--------|-------------|
| Run 1 (Baseline) | nomic-embed-text, chunk=300, k=5, qwen | 48% |
| Run 2 | nomic→bge-m3 | 65% |
| Run 3 | bge-m3, chunk=1000 | 94% |
| Run 8 (full dataset, 40 questions) | bge-m3, chunk=1000, k=5 | 60–64% |
| Retrieval Check 10.06. | bge-m3, chunk=1000, k=5 | 70% hit rate |

**Run C (the final grid run, 18.–20.06.2026):** 293 questions, 20 parameter combinations, 5,860 runs. Result: parameter differences are at most 0.07 points — statistically irrelevant. The `susi` category at 98% is the weakest; all others at 99–100%.

### The Key Finding: Document Quality Beats Model Size

On 10.06.2026 the impact of SUSIpedia document quality on retrieval hit rate was directly measured:

```
Retrieval Hit Rate development:

Start (unstructured, 230 questions):         36%
After cleanup (encoding fixes, duplicates):  53%
After SUSIpedia rewrite + chunk=1000:        91%
                                           ──────
Total improvement:                          +55 percentage points
```

No better model was deployed. The same stack (bge-m3, qwen2.5-coder:7b, ChromaDB), the same hardware — only better source documents and larger chunks.

This is a direct empirical proof of the project's core thesis: **the knowledge base is the most important factor in a RAG system** — more important than the embedding model, more important than the LLM, more important than prompt engineering.

---

## Chapter 05 — Dead Ends and New Architecture

### Four Discarded Approaches

**Dead End A — Fully Automated Auto-Save Pipeline (Self-Poisoning):** SUSI was to decide autonomously when to write a conversation back to SUSIpedia as Markdown. The problem: when the chat model hallucinates, it writes its own errors into long-term memory undetected. A destructive feedback loop that amplifies itself. Deactivated May 2026.

**Dead End B — Consolidation by the Same LLM:** New knowledge should be fused with existing documents by the chat model itself. The problem: it is structurally illogical to use the same model that makes errors in chat as an error-free editor. The model focuses so heavily on the new knowledge that it simply deletes or forgets old fundamental facts. Regression errors are nearly undetectable because the merged version is syntactically correct and plausible — but old facts are missing.

**Dead End C — Blind Appending:** New insights appended chronologically with a timestamp to the master file. The problem: creates redundancy and contradictions within the same file. When section 1 (March) says "use function X" and section 5 (June) says "use Y instead of X," the RAG feeds the LLM with contradictory chunks from the same file. The model has no mechanism to determine which chunk is more recent — it guesses.

**Dead End D — Pure Mathematical Filters:** Cosine similarity as the sole quality filter. The problems: false alarms block valid additions that happen to be vectorially close to existing content. Silent failures let through garbage because a typo changes the vector just enough. Filter overload: the developer ends up manually reviewing the filter's decisions anyway — with less context than direct manual review would provide.

### The New Target Architecture — 3-Stage Memory Model

```
Chat history
     ↓
[Stage 1] Short-term memory (SQLite — persistent, local)
     ↓  (explicit !save command)
[Stage 2] Model switch + automated gatekeeper (quarantine)
     ↓  (NLI/Cross-Encoder check passed)
[Stage 3] Human-in-the-Loop review (SusiInbox in dashboard)
     ↓  (one-click approval)
SUSIpedia (.md) → ingest.py → ChromaDB
```

The AI is a highly efficient secretary that drafts and pre-validates proposals. The human retains absolute data sovereignty over long-term memory. This is not a compromise — it is the correct design principle for a system that must remain reliably trustworthy.

---

## Chapter 06 — Limits and Honest Role Definition

SUSI is not a GPT-4 replacement. This was never the goal.

| Task | SUSI | Claude / ChatGPT |
|------|------|-----------------|
| Personal memory | ✅ | ❌ |
| Retrieving project documentation | ✅ | ❌ |
| Local processing without cloud | ✅ | ❌ |
| Code review, complex debugging | ❌ | ✅ |
| Explaining new technical concepts | ❌ | ✅ |

SUSI and external AI assistants are complementary, not competitive. The combination is stronger than either system alone.

---

## Chapter 07 — Roadmap

### Phase 1 — Stable Foundation (Q3 2026)

✅ SUSIpedia quality — all 124 files rewritten, 617 chunks, hit rate 91%  
✅ MMR vs. Similarity — evaluated (Lauf C): similarity marginally better (3.01 vs. 2.99), difference statistically irrelevant  
✅ Cross-Encoder Reranker — bge-reranker-v2-m3 productive at 97% correctness  
✅ Router — retrieval-driven profile system with 5 categories, implemented 20.06.2026  
✅ Query Rewriting — active, resolves first-person references and follow-up questions  
✅ Fallback profile — out-of-scope questions handled via `praezise_hybrid` prompt  
✅ Chat history in rewriter — last 2 Q/A pairs passed to rewriter, answers truncated to 200 characters  
❌ Metrics consistency in evaluator — `--nachbewertung` scale (0–2) not yet unified with main system (0–3)  
❌ Async worker for model switching (`!save` command) — planned Q3 2026

### Phase 2 — 3-Stage Memory Model (Q4 2026)

Full implementation of the Human-in-the-Loop save architecture: SQLite short-term memory, automated multilingual cross-encoder gatekeeper, SusiInbox dashboard for one-click review.

### Phase 3 — Retrieval Architecture Extensions (2027)

PDF-RAG (separate ChromaDB index per document), Hybrid Search (BM25 + vector, potentially requiring migration from ChromaDB to Weaviate or Qdrant), and further category-specific optimizations — only after Phase 2 is complete and the gatekeeper has processed at least 30 validated saves without detected hallucination.

### Phase 4 — Edge Deployment and Physical Integration (long-term)

Small quantized models (1B–3B parameters) on Raspberry Pi 5 as MCP server. Whisper for voice control (local speech-to-text), GPIO integration for Smart Home, camera-based scene recognition. Inference tasks must be scheduled sequentially — the Pi 5 cannot handle parallel LLM and Whisper load.

**Business potential:** The SUSI architecture is directly transferable to enterprise environments. SMEs under GDPR, the AI Act, and trade secret law need local AI solutions — and existing alternatives like Microsoft Copilot are cloud-bound. A local, GDPR-compliant RAG assistant where the knowledge base is a permanently owned enterprise asset is strategically attractive.

---

## Chapter 08 — From Evaluated System to Production Assistant (June 2026)

### Reranker Evolution

| Stage | Model | Result |
|-------|-------|--------|
| 1 (12.06.) | ms-marco-MiniLM | English-only — unsuitable for German content |
| 2 (18.06.) | amberoad/bert-multilingual | 59% correctness WITH reranker vs. 100% WITHOUT — actively harmful |
| 3 (18.06.) | **BAAI/bge-reranker-v2-m3** | **97% correctness** ✅ |

Key lesson: **a bad reranker is worse than no reranker.** The reranker must match the embedding model and the document language. A smoke test is mandatory before any production deployment.

### Model Comparison: qwen2.5-coder:7b vs. llama3.1:8b

**qwen2.5-coder:7b — the precision specialist:** Token-efficient (63 tokens vs. 236 for the same information). Short and precise on factual questions. Respects the language of the question (German, English, French, Italian, Spanish tested). Optimal at temperature 0.0. Fewer hallucinations on facts.

**llama3.1:8b — the analyst:** Connects information from multiple sources on multi-document questions. More nuanced reasoning on personal reflection. Ignores the multilingual prompt and always answers in German regardless of input language. Temperature 0.3 better suited for analytical questions.

### Run C Results Summary

5,860 runs across 20 parameter combinations confirm: parameter differences are at most 0.07 points. The largest lever was document quality (hit rate 36% → 91%), not model tuning. The parameter optimization phase is complete.

### Next: Run D

Run D shifts focus from parameter optimization to quality measurement of the new production components: router profile accuracy (validated against manual gold-standard assignments), qwen3 model comparison (qwen2.5-coder:7b vs. qwen3:14b), thinking mode on/off impact, and targeted miss analysis of the `susi` category (weakest at 98%).

---

## Five Core Findings

1. **The knowledge base is the asset** — not the model. Owning SUSIpedia means independence from model updates and provider decisions.
2. **Document quality beats model size** — well-written prose retrieves better than compact lists, regardless of how good the embedding model is. Empirically proven: +55 percentage points in hit rate through document quality alone.
3. **Measure retrieval before generation** — what retrieval does not find, no prompt can repair. Understand the retrieval layer first, then optimize.
4. **Human-in-the-Loop is not a compromise** — it is the correct design principle for a system that must remain reliably trustworthy over time.
5. **Simplicity is an architectural decision** — one model that works well beats three agents that interfere with each other.

---

*Status: June 2026 — document updated continuously*  
*Martin Freimuth · github.com/Martin-Frei · Stack: Python · Django · HTMX · LangChain · ChromaDB · Ollama · bge-reranker-v2-m3*