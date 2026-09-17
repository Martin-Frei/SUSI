# SUSI Eval Dashboard

Interactive React dashboard for configuring, monitoring, and analyzing evaluation runs of the SUSI RAG pipeline.

## Stack

- **React 19** + Vite + Tailwind CSS v4
- **Chart.js** (Canvas-based boxplots, scatter plots)
- **Django REST API** on `127.0.0.1:8008` (backend in `eval/`)

## Quick Start

```bash
cd susi_frontend
npm install
npm run dev
```

Create `.env` in `susi_frontend/`:
```dotenv
VITE_API_URL=http://127.0.0.1:8008/api/eval
```

Start Django backend on port 8008:
```bash
cd ..
python manage.py runserver 8008
```

## Architecture

```
React Frontend  ←→  Django REST API  ←→  Background Worker  ←→  SUSI RAG Pipeline
  (Polling 3s)       (Endpoints)         (Django-Q)              (Ollama + ChromaDB)
```

## Four Dashboard Modes

### 1. Parameter Mode (Landing Page)
Configure and start evaluation runs. Left sidebar with 7 sections:
- **Run Name** — auto-generated from date + question set + non-default params
- **Question Set** — dropdown with preview modal
- **Models** — checkboxes from Ollama, embedding models filtered out
- **Parameters** — clickable chip groups for `top_k`, `temperature`, `num_ctx`, `system_prompt`, `thinking` with `[+]` for custom values
- **Pipeline Toggles** — 3-way switches (On/Off/Both) for Reranker, Rewriter, Router, agent_datum, agent_pedia
- **Grid Preview** — live calculation of combinations × questions = total runs + estimated duration
- **Start Button** — POST to `/runs/`, transitions to Live Mode

### 2. Live Mode
Real-time monitoring of a running evaluation. Layout: header full width, charts left 50%, terminal right 50%.
- **Header** — progress bar, 5 KPI cards (Remaining, Avg/Q, Min, Max, tok/s), abort button
- **Boxplot Charts** — one per variable parameter, tabs for auto_score / BERT / ROUGE-L
- **Category Boxplot** — horizontal, dynamic categories
- **Scatter Plot** — response time per question, colored by model, hoverable
- **Terminal** — log feed with score color-coding, auto-scroll, search filter

### 3. Result Mode
Full analysis of a completed run.
- **Filter Bar** — category, model, score presets, sort by any column, CSV export
- **Summary Cards** — Accuracy%, Avg Score, Avg BERT, Avg Time, Avg tok/s
- **Charts** — reuses LiveCharts with complete data
- **Drill-Down Table** — expandable rows showing answer vs. reference, router profile, sources
- **Detail Modal** — slide-over with all metrics, pipeline info, V2 placeholder for chunks

### 4. Compare Mode
Side-by-side comparison of up to 3 runs.
- **Run Selectors** — Baseline A (all runs), Challenger B + C (same question set only)
- **Parameter Intersection** — only values present in ALL selected runs are clickable; missing values are disabled with tooltip
- **Delta Table** — score per run + delta vs. baseline, color-coded (green ↑, red ↓, gray =)
- **Filter Chips** — All / Regressions / Improvements
- **Expandable Rows** — answers side-by-side (2 or 3 columns) + reference

## Project Structure

```
susi_frontend/
├── .env                                 # VITE_API_URL
├── package.json
├── services/
│   └── api.js                           # Central API layer (15 functions)
└── src/
    ├── App.jsx                          # Root: mode switching + top navigation
    ├── App.css                          # Minimal beyond Tailwind
    ├── index.css                        # Tailwind + SUSI color theme
    ├── main.jsx                         # React entry point
    ├── components/
    │   ├── ConfigSidebar.jsx            # Layout wrapper for config sections 1–7
    │   ├── ModelSelector.jsx            # Checkbox list for Ollama models
    │   ├── ParamChips.jsx               # Clickable preset chips + custom input
    │   ├── PipelineToggles.jsx          # 3-way segmented controls (On/Off/Both)
    │   ├── GridPreview.jsx              # Live grid calculation display
    │   ├── QuestionSetPicker.jsx        # Dropdown + preview button
    │   ├── QuestionPreviewModal.jsx     # Read-only question list modal
    │   ├── LiveHeaderBar.jsx            # Progress + 5 KPIs + abort
    │   ├── LiveCharts.jsx               # Boxplots + scatter (Canvas, no framework)
    │   ├── LiveTerminal.jsx             # Log feed with auto-scroll + search
    │   ├── LiveParameterSidebar.jsx     # Collapsible read-only config view
    │   ├── ResultFilterBar.jsx          # Filters, sort, export, compare, delete
    │   ├── ResultTable.jsx              # Sortable table with expandable rows
    │   └── ResultDetailModal.jsx        # Slide-over detail inspector
    └── pages/
        ├── ParameterMode.jsx            # Landing page with all config state
        ├── LiveMode.jsx                 # Polling + data distribution
        ├── ResultMode.jsx               # Filtering + analysis
        └── CompareMode.jsx              # A/B/C comparison with param intersection
```

## API Endpoints

All endpoints live under the base URL from `.env` (default: `http://127.0.0.1:8008/api/eval`).

| Function | Method | Endpoint | Purpose |
|---|---|---|---|
| `getModels()` | GET | `/models/` | Ollama models, embeddings filtered |
| `getQuestionSets()` | GET | `/questionsets/` | List all question sets |
| `getQuestionSetDetail(id)` | GET | `/questionsets/<id>/` | Single set with questions |
| `uploadQuestionSet()` | POST | `/questionsets/` | Upload new set |
| `deleteQuestionSet(id)` | DELETE | `/questionsets/<id>/` | Delete set |
| `getRuns()` | GET | `/runs/` | List all runs |
| `startRun()` | POST | `/runs/` | Start new run |
| `getRunStatus(id)` | GET | `/runs/<id>/status/` | Progress + last 10 results |
| `getRunResults(id)` | GET | `/runs/<id>/results/` | Filtered results |
| `abortRun(id)` | POST | `/runs/<id>/abort/` | Abort running run |
| `deleteRun(id)` | DELETE | `/runs/<id>/` | Delete run |

## Utilities

| Function | Purpose |
|---|---|
| `pollRunStatus(runId, onUpdate, intervalMs)` | Auto-polling, stops on terminal state, returns `stop()` |
| `generateRunName(qsName, models, params, pipeline)` | Auto-name from non-default params |
| `calculateGrid(models, params, pipeline, qCount)` | Client-side grid size + duration estimate |
| `formatDuration(seconds)` | Seconds → readable string (`~12 Minuten`) |

## Color Theme

| Token | Hex | Usage |
|---|---|---|
| `primary_gold` | `#9A7000` | Brand accent, active states, tok/s |
| `dark_background` | `#12122a` | Page background |
| `surface_dark` | `#1a1a2e` | Cards, inputs, chart backgrounds |
| `terminal_green` | `#4CAF50` | Score ≥3, "On" toggles, improvements |
| `terminal_orange` | `#FF9800` | Score 2, "Both" toggles, warnings |
| `terminal_red` | `#f44336` | Score ≤1, "Off" toggles, regressions |
| `terminal_gray` | `#666` | Labels, disabled states |

## V2 Roadmap

- [ ] Chunk text + reranker scores in ResultDetailModal
- [ ] Clickable legend in scatter plot (highlight/filter by model or category)
- [ ] Radar chart in CompareMode (categories as axes)
- [ ] Right-side run history in ParameterMode
- [ ] Automated tests in `tests.py`
- [ ] Dynamic `num_ctx` based on actual chunk tokens

---

*Part of the [SUSI](https://github.com/Martin-Frei/SUSI) project — a fully local, GDPR-compliant RAG assistant.*
*Martin Freimuth · September 2026*