// susi_frontend/services/api.js

// ============================================================
// SUSI Eval Dashboard — API Layer
//
// Central fetch wrapper + all endpoint functions for the
// React eval dashboard. Base URL from .env includes /api/eval,
// so endpoints are short: /models/, /runs/, /questionsets/.
//
// .env: VITE_API_URL=http://127.0.0.1:8008/api/eval
// ============================================================

const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8008/api/eval").replace(/\/+$/, "");

// --- Core Fetch Wrapper --------------------------------------
// All API calls go through this. Handles JSON serialization,
// error extraction, and 204 No Content for DELETE responses.

async function apiRequest(endpoint, options = {}) {
  const { method = "GET", body, headers = {} } = options;

  const config = {
    method,
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
  };

  if (body) {
    config.body = JSON.stringify(body);
  }

  const response = await fetch(`${API_URL}${endpoint}`, config);

  if (response.status === 204) return null;

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || error.error || `API ${response.status}: ${response.statusText}`);
  }

  return response.json();
}

// --- Ollama Models -------------------------------------------
// Returns all models pulled in Ollama, filtered to exclude
// embedding models (< 1.5 GB). Used by ModelSelector checkboxes.

export async function getModels() {
  const data = await apiRequest("/models/");
  const models = data.models || [];
  return models.filter((m) => m.size_gb >= 1.5);
}

// --- Question Sets -------------------------------------------
// CRUD for evaluation question sets (JSON files with questions,
// reference answers, and categories).

export async function getQuestionSets() {
  return apiRequest("/questionsets/");
}

export async function getQuestionSetDetail(id) {
  return apiRequest(`/questionsets/${id}/`);
}

export async function uploadQuestionSet({ name, description = "", questions }) {
  return apiRequest("/questionsets/", {
    method: "POST",
    body: {
      name,
      description,
      questions_json: JSON.stringify(questions),
    },
  });
}

export async function deleteQuestionSet(id) {
  return apiRequest(`/questionsets/${id}/`, { method: "DELETE" });
}

// --- Eval Runs -----------------------------------------------
// Start, monitor, and manage evaluation runs. A run tests one
// or more model × parameter × pipeline combinations against
// a question set.

export async function getRuns() {
  return apiRequest("/runs/");
}

// Starts a new eval run. Body contains the full grid config:
// models, params (top_k, temp, ...), pipeline toggles, question set.
// Returns { id, status } — use pollRunStatus() to track progress.
export async function startRun({ name = "", question_set_id, models, params, pipeline }) {
  return apiRequest("/runs/", {
    method: "POST",
    body: { name, question_set_id, models, params, pipeline },
  });
}

// Returns current progress: { status, progress, current_question, ... }
// Status is one of: pending, running, completed, failed, aborted.
export async function getRunStatus(runId) {
  const data = await apiRequest(`/runs/${runId}/status/`);

  // Normalize recent_results field names for LiveMode
  if (data.recent_results && Array.isArray(data.recent_results)) {
    data.recent_results = data.recent_results.map(normalizeResult);
  }

  return data;
}

// --- Result Field Normalizer ----------------------------------
// Maps backend field names to the names used in all frontend
// components. Single source of truth for the mapping — if the
// backend changes a field name, fix it here only.

function normalizeResult(r) {
  return {
    ...r,
    model: r.model_name ?? r.model,
    question: r.question_text ?? r.question,
    kategorie: r.question_category ?? r.kategorie,
    referenz: r.reference_answer ?? r.referenz,
    answer: r.answer_text ?? r.answer,
    router_profil: r.router_profile ?? r.router_profil,
    score: r.auto_score ?? r.score,
    time: r.response_time_sec ?? r.time,
    tok_s: r.tok_per_sec ?? r.tok_s,
    // These stay the same but listed for clarity:
    bert_score: r.bert_score,
    rouge_l: r.rouge_l,
    sources: r.sources,
    rewritten_query: r.rewritten_query,
    params: r.params,
    pipeline: r.pipeline,
    index: r.id ?? r.index,
  };
}

// Returns scored results with optional filters.
// filters: { model, category, min_score, max_score }
export async function getRunResults(runId, filters = {}) {
  const queryParams = new URLSearchParams();

  if (filters.model) queryParams.set("model", filters.model);
  if (filters.category) queryParams.set("category", filters.category);
  if (filters.min_score != null) queryParams.set("min_score", filters.min_score);
  if (filters.max_score != null) queryParams.set("max_score", filters.max_score);

  const qs = queryParams.toString();
  const data = await apiRequest(`/runs/${runId}/results/${qs ? `?${qs}` : ""}`);

  // Normalize field names for all frontend components
  const raw = Array.isArray(data) ? data : data.results || [];
  return raw.map(normalizeResult);
}

export async function abortRun(runId) {
  return apiRequest(`/runs/${runId}/abort/`, { method: "POST" });
}

export async function deleteRun(runId) {
  return apiRequest(`/runs/${runId}/`, { method: "DELETE" });
}

// --- Polling Helper ------------------------------------------
// Polls run status every `intervalMs` ms. Calls `onUpdate(status)`
// on each poll. Auto-stops on completed/failed/aborted.
// Returns a stop() function for manual cleanup.
//
// Usage:
//   const stop = pollRunStatus(9, (s) => setStatus(s));
//   // later: stop();

export function pollRunStatus(runId, onUpdate, intervalMs = 3000) {
  let timer = null;
  let stopped = false;

  const poll = async () => {
    if (stopped) return;

    try {
      const status = await getRunStatus(runId);
      onUpdate(status);

      if (["completed", "failed", "aborted"].includes(status.status)) {
        stopped = true;
        return;
      }
    } catch (err) {
      console.error("Polling error:", err);
    }

    if (!stopped) {
      timer = setTimeout(poll, intervalMs);
    }
  };

  poll();

  return () => {
    stopped = true;
    if (timer) clearTimeout(timer);
  };
}

// --- Run Name Generator --------------------------------------
// Builds a descriptive run name from date, question set, models,
// and ONLY non-default parameters. If everything is at defaults,
// the name stays short: "2026-09-14_Datumsarithmetik_qwen2.5-coder"
//
// Non-defaults are appended as suffixes:
//   "_k5-9"          → top_k changed to [5, 9]
//   "_t0.3"          → temperature changed to 0.3
//   "_reranker-both" → pipeline toggle set to both (on + off)

const PARAM_DEFAULTS = {
  top_k: 7,
  temperature: 0.0,
  num_ctx: 4096,
  system_prompt: "praezise_neu",
  thinking: false,
};

const PIPELINE_DEFAULTS = {
  reranker: true,
  rewriter: true,
  router: true,
  agent_datum: true,
  agent_pedia: false,
};

export function generateRunName(questionSetName, models, params, pipeline) {
  const today = new Date().toISOString().slice(0, 10);

  // Shorten model names: "qwen2.5-coder:7b" → "qwen2.5-coder"
  const shortModels = models.map((m) => m.split(":")[0]);
  const modelPart = shortModels.join("+");

  // Collect non-default parameter diffs
  const diffs = [];

  const paramLabels = { top_k: "k", temperature: "t", num_ctx: "ctx" };

  for (const [key, defaultVal] of Object.entries(PARAM_DEFAULTS)) {
    const values = params[key];
    if (!values || values.length === 0) continue;

    if (key === "thinking") {
      if (values.length === 2) diffs.push("thinking-both");
      else if (values[0] === true) diffs.push("thinking-on");
    } else if (key === "system_prompt") {
      if (values.length > 1) diffs.push(`prompt-${values.length}x`);
      else if (values[0] !== defaultVal) diffs.push(values[0]);
    } else {
      // Numeric params: only add if not single default value
      const isDefault = values.length === 1 && values[0] === defaultVal;
      if (!isDefault) {
        const label = paramLabels[key] || key;
        diffs.push(`${label}${values.join("-")}`);
      }
    }
  }

  // Pipeline diffs: "both" if [true, false], else "on"/"off" if flipped
  for (const [key, defaultVal] of Object.entries(PIPELINE_DEFAULTS)) {
    const values = pipeline[key];
    if (!values || values.length === 0) continue;

    if (values.length === 2) {
      diffs.push(`${key}-both`);
    } else if (values[0] !== defaultVal) {
      diffs.push(`${key}-${values[0] ? "on" : "off"}`);
    }
  }

  return [today, questionSetName, modelPart, ...diffs].join("_");
}

// --- Grid Calculation (client-side) --------------------------
// Computes total number of runs from the current config.
// Used by GridPreview to show live feedback while the user
// clicks chips and toggles.
//
// Formula: models × param_combos × pipeline_combos × questions
// Estimate: ~12 seconds per question (single GPU, 7b model)

export function calculateGrid(models, params, pipeline, questionCount) {
  const paramCombos = Object.values(params).reduce((acc, arr) => acc * arr.length, 1);
  const pipelineCombos = Object.values(pipeline).reduce((acc, arr) => acc * arr.length, 1);
  const totalCombinations = models.length * paramCombos * pipelineCombos;
  const totalRuns = totalCombinations * questionCount;
  const estimatedSeconds = totalRuns * 12;

  return { totalCombinations, totalRuns, estimatedSeconds };
}

// Formats seconds into a readable German string.
// 90 → "~2 Minuten", 3600 → "~1 Stunde", 5400 → "~1,5 Stunden"
export function formatDuration(seconds) {
  if (seconds < 60) return `~${seconds} Sekunden`;
  if (seconds < 3600) return `~${Math.ceil(seconds / 60)} Minuten`;
  const hours = (seconds / 3600).toFixed(1).replace(".", ",");
  return `~${hours} Stunden`;
}

