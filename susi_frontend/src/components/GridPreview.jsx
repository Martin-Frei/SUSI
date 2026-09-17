//susi_frontend/src/components/GridPreview.jsx


// ============================================================
// GridPreview — Section 6 of ConfigSidebar
//
// Displays a live-updating summary of the current grid config:
// how many models, param combos, pipeline combos, total runs,
// and estimated duration. Recalculates on every state change
// (no API call — pure client-side math via calculateGrid).
//
// Props:
//   selectedModels — string[] of selected model names
//   params         — { top_k: [7], temperature: [0.0, 0.3], ... }
//   pipeline       — { reranker: [true], rewriter: [true, false], ... }
//   questionCount  — number of questions in selected question set
// ============================================================

import { calculateGrid, formatDuration } from "../../services/api";

export default function GridPreview({ selectedModels = [], params = {}, pipeline = {}, questionCount = 0 }) {

  const modelCount = selectedModels.length;

  // Count individual dimension sizes for the breakdown
  const paramCounts = {
    top_k: (params.top_k || [7]).length,
    temperature: (params.temperature || [0.0]).length,
    num_ctx: (params.num_ctx || [4096]).length,
    system_prompt: (params.system_prompt || ["praezise_neu"]).length,
    thinking: (params.thinking || [false]).length,
  };

  const pipelineCounts = {
    reranker: (pipeline.reranker || [true]).length,
    rewriter: (pipeline.rewriter || [true]).length,
    router: (pipeline.router || [true]).length,
    agent_datum: (pipeline.agent_datum || [true]).length,
    agent_pedia: (pipeline.agent_pedia || [false]).length,
  };

  const { totalCombinations, totalRuns, estimatedSeconds } =
    calculateGrid(selectedModels, params, pipeline, questionCount);

  // Build the multiplication breakdown string
  // Only show dimensions with more than 1 value (contributing to grid)
  const parts = [];
  if (modelCount > 1) parts.push(`${modelCount} models`);

  for (const [key, count] of Object.entries(paramCounts)) {
    if (count > 1) parts.push(`${count} ${key}`);
  }
  for (const [key, count] of Object.entries(pipelineCounts)) {
    if (count > 1) parts.push(`${count} ${key}`);
  }

  const isGrid = totalCombinations > 1;
  const isReady = modelCount > 0 && questionCount > 0;

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-terminal_txt_gold uppercase tracking-wide">
        Grid Preview
      </h3>

      <div className={`
        rounded p-3 space-y-2 border
        ${isReady
          ? "bg-surface_dark border-terminal_gray/20"
          : "bg-surface_dark/50 border-terminal_red/30"
        }
      `}>
        {!isReady ? (
          <p className="text-xs text-terminal_red">
            {modelCount === 0 && questionCount === 0
              ? "Select a model and question set"
              : modelCount === 0
                ? "Select at least one model"
                : "Select a question set"
            }
          </p>
        ) : (
          <>
            {/* Breakdown line */}
            {isGrid && parts.length > 0 && (
              <p className="text-xs text-terminal_gray">
                {parts.join(" × ")}
              </p>
            )}

            {/* Main numbers */}
            <div className="flex justify-between items-baseline">
              <span className="text-xs text-terminal_gray">Combinations</span>
              <span className={`text-sm font-mono font-semibold ${isGrid ? "text-terminal_orange" : "text-white"}`}>
                {totalCombinations}
              </span>
            </div>

            <div className="flex justify-between items-baseline">
              <span className="text-xs text-terminal_gray">Total runs</span>
              <span className="text-sm font-mono font-semibold text-white">
                {totalRuns.toLocaleString("de-DE")}
              </span>
            </div>

            <div className="flex justify-between items-baseline">
              <span className="text-xs text-terminal_gray">
                {questionCount} question{questionCount !== 1 ? "s" : ""} × {totalCombinations} combo{totalCombinations !== 1 ? "s" : ""}
              </span>
            </div>

            {/* Duration estimate */}
            <div className="pt-1 border-t border-terminal_gray/15">
              <div className="flex justify-between items-baseline">
                <span className="text-xs text-terminal_gray">Estimated</span>
                <span className={`text-sm font-semibold ${
                  estimatedSeconds > 3600
                    ? "text-terminal_red"
                    : estimatedSeconds > 600
                      ? "text-terminal_orange"
                      : "text-terminal_green"
                }`}>
                  {formatDuration(estimatedSeconds)}
                </span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
