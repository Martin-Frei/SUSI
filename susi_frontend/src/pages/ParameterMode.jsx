// susi_frontend/src/pages/ParameterMode.jsx

// ============================================================
// ParameterMode — Landing Page (State 1)
//
// Holds ALL config state for the eval run. Left side: ConfigSidebar
// with all 7 sections. Right side: last run results or empty state.
//
// On mount, fetches models, question sets, and recent runs.
// On "Start": generates run name (if empty), POSTs to /runs/,
// and calls onStartRun(runId) to transition to Live mode.
//
// Props:
//   onStartRun — callback(runId: number) — parent switches to LiveMode
// ============================================================

import { useState, useEffect } from "react";
import ConfigSidebar from "../components/ConfigSidebar";
import {
  getModels,
  getQuestionSets,
  getQuestionSetDetail,
  getRuns,
  startRun,
  generateRunName,
} from "../../services/api";

// Default parameter values matching SUSI pipeline config
const DEFAULT_PARAMS = {
  top_k: [7],
  temperature: [0.0],
  num_ctx: [4096],
  system_prompt: ["praezise_neu"],
  thinking: [false],
};

const DEFAULT_PIPELINE = {
  reranker: [true],
  rewriter: [true],
  router: [true],
  agent_datum: [true],
  agent_pedia: [false],
};

export default function ParameterMode({ onStartRun, onViewResult }) {
  // --- Data from API -----------------------------------------
  const [models, setModels] = useState([]);
  const [modelsLoading, setModelsLoading] = useState(true);

  const [questionSets, setQuestionSets] = useState([]);
  const [questionSetLoading, setQuestionSetLoading] = useState(true);

  const [questionDetail, setQuestionDetail] = useState(null);
  const [questionDetailLoading, setQuestionDetailLoading] = useState(false);

  const [recentRuns, setRecentRuns] = useState([]);

  // --- User selections ----------------------------------------
  const [runName, setRunName] = useState("");
  const [selectedQuestionSetId, setSelectedQuestionSetId] = useState(null);
  const [selectedModels, setSelectedModels] = useState([]);
  const [params, setParams] = useState(DEFAULT_PARAMS);
  const [pipeline, setPipeline] = useState(DEFAULT_PIPELINE);

  // --- UI state -----------------------------------------------
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState(null);

  // --- Fetch initial data on mount ----------------------------

  useEffect(() => {
    async function loadModels() {
      try {
        const data = await getModels();
        setModels(data);
      } catch (err) {
        console.error("Failed to load models:", err);
      } finally {
        setModelsLoading(false);
      }
    }

    async function loadQuestionSets() {
      try {
        const data = await getQuestionSets();
        setQuestionSets(data);
      } catch (err) {
        console.error("Failed to load question sets:", err);
      } finally {
        setQuestionSetLoading(false);
      }
    }

    async function loadRuns() {
      try {
        const data = await getRuns();
        setRecentRuns(data);
      } catch (err) {
        console.error("Failed to load runs:", err);
      }
    }

    loadModels();
    loadQuestionSets();
    loadRuns();
  }, []);

  // --- Derived values -----------------------------------------

  const selectedSet = questionSets.find(
    (qs) => qs.id === selectedQuestionSetId
  );
  const questionCount = selectedSet?.question_count || 0;
  const canStart = selectedModels.length > 0 && selectedQuestionSetId !== null;

  // --- Handlers -----------------------------------------------

  const handlePreviewRequest = async (id) => {
    setQuestionDetailLoading(true);
    try {
      const data = await getQuestionSetDetail(id);
      setQuestionDetail(data);
    } catch (err) {
      console.error("Failed to load question set detail:", err);
    } finally {
      setQuestionDetailLoading(false);
    }
  };

  const handleStart = async () => {
    if (!canStart) return;

    setStarting(true);
    setError(null);

    try {
      // Generate run name if user left it empty
      const name =
        runName ||
        generateRunName(
          selectedSet?.name || "Eval",
          selectedModels,
          params,
          pipeline
        );

      const result = await startRun({
        name,
        question_set_id: selectedQuestionSetId,
        models: selectedModels,
        params,
        pipeline,
      });

      // Transition to Live mode
      onStartRun(result.id);
    } catch (err) {
      setError(err.message);
      console.error("Failed to start run:", err);
    } finally {
      setStarting(false);
    }
  };

  // --- Render -------------------------------------------------

  return (
    <div className="flex h-full">
      {/* Left: Config Sidebar */}
      <ConfigSidebar
        runName={runName}
        onRunNameChange={setRunName}
        questionSets={questionSets}
        selectedQuestionSetId={selectedQuestionSetId}
        onQuestionSetChange={setSelectedQuestionSetId}
        questionSetLoading={questionSetLoading}
        questionDetail={questionDetail}
        questionDetailLoading={questionDetailLoading}
        onPreviewRequest={handlePreviewRequest}
        models={models}
        selectedModels={selectedModels}
        onModelsChange={setSelectedModels}
        modelsLoading={modelsLoading}
        params={params}
        onParamsChange={setParams}
        pipeline={pipeline}
        onPipelineChange={setPipeline}
        questionCount={questionCount}
        onStart={handleStart}
        canStart={canStart}
        starting={starting}
      />

      {/* Right: Main area — last run results or empty state */}
      <main className="flex-1 h-full overflow-y-auto bg-dark_background p-6">
        {/* Error banner */}
        {error && (
          <div className="mb-4 px-4 py-3 rounded bg-terminal_red/10 border border-terminal_red/30">
            <p className="text-sm text-terminal_red">{error}</p>
          </div>
        )}

        {/* Recent runs dropdown */}
        {recentRuns.length > 0 && (
          <div className="mb-6">
            <label className="text-xs text-terminal_gray block mb-1">
              Last runs
            </label>
            <select
              className="px-3 py-2 rounded text-sm
        bg-surface_dark border border-terminal_gray/20 text-white
        focus:outline-none focus:border-primary_gold
        appearance-none cursor-pointer"
              defaultValue=""
              onChange={(e) => {
                if (e.target.value) onViewResult(Number(e.target.value));
              }}
            >
              <option value="" disabled>
                Select a past run…
              </option>
              {recentRuns.map((run) => (
                <option key={run.id} value={run.id}>
                  {run.name || `Run #${run.id}`} — {run.status}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Empty state */}
        {recentRuns.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="text-6xl mb-4 opacity-20">🔬</div>
            <h2 className="text-lg font-semibold text-white mb-2">
              No evaluation runs yet
            </h2>
            <p className="text-sm text-terminal_gray max-w-md">
              Configure your models, parameters, and pipeline settings in the
              sidebar, then start your first evaluation run.
            </p>
          </div>
        )}

        {/* TODO: Show last run results here when a run is selected */}
      </main>
    </div>
  );
}
