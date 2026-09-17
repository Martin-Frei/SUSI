// susi_frontend/src/components/LiveParameterSiedeBar.jsx


// ============================================================
// LiveParameterSidebar — Left panel of Live Mode
//
// Narrow collapsed sidebar (~36px) that expands on click to
// show the active run configuration in read-only mode.
// Lets the user check what's running without going back to
// Parameter Mode.
//
// Props:
//   config — the run configuration object:
//            { name, models, params, pipeline, question_set_name, question_count }
// ============================================================

import { useState } from "react";

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

export default function LiveParameterSidebar({ config = {} }) {
  const [expanded, setExpanded] = useState(false);

  const { name, models = [], params = {}, pipeline = {}, question_set_name, question_count } = config;

  // Check if a param value differs from default
  const isNonDefault = (key, values) => {
    const def = PARAM_DEFAULTS[key];
    if (def === undefined) return true;
    if (!values || values.length === 0) return false;
    if (values.length > 1) return true;
    return values[0] !== def;
  };

  const isPipelineNonDefault = (key, values) => {
    const def = PIPELINE_DEFAULTS[key];
    if (def === undefined) return true;
    if (!values || values.length === 0) return false;
    if (values.length > 1) return true;
    return values[0] !== def;
  };

  return (
    <aside
      className={`
        shrink-0 h-full border-r border-terminal_gray/15 bg-dark_background
        transition-all duration-200 overflow-hidden
        ${expanded ? "w-64" : "w-9"}
      `}
    >
      {/* Toggle button */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-center py-3
          text-terminal_gray hover:text-primary_gold transition-colors"
        title={expanded ? "Collapse sidebar" : "Show run config"}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg" width="16" height="16"
          viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
          className={`transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
        >
          <polyline points="9 18 15 12 9 6" />
        </svg>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-3 pb-4 space-y-4 overflow-y-auto h-[calc(100%-44px)]">

          {/* Run name */}
          {name && (
            <div>
              <p className="text-xs text-terminal_gray mb-0.5">Run</p>
              <p className="text-sm text-white font-mono truncate">{name}</p>
            </div>
          )}

          {/* Question set */}
          <div>
            <p className="text-xs text-terminal_gray mb-0.5">Question set</p>
            <p className="text-sm text-white">
              {question_set_name || "—"}
              {question_count > 0 && (
                <span className="text-terminal_gray ml-1">({question_count})</span>
              )}
            </p>
          </div>

          {/* Models */}
          <div>
            <p className="text-xs text-terminal_gray mb-1">Models</p>
            <div className="space-y-0.5">
              {models.map((m) => (
                <p key={m} className="text-sm text-white font-mono truncate">{m}</p>
              ))}
            </div>
          </div>

          {/* Parameters — highlight non-defaults */}
          <div>
            <p className="text-xs text-terminal_gray mb-1">Parameters</p>
            <div className="space-y-1">
              {Object.entries(params).map(([key, values]) => {
                if (!values || values.length === 0) return null;
                const nonDefault = isNonDefault(key, values);
                const display = values.length > 1
                  ? values.join(", ")
                  : String(values[0]);

                return (
                  <div key={key} className="flex justify-between text-sm">
                    <span className="text-terminal_gray">{key}</span>
                    <span className={`font-mono ${nonDefault ? "text-terminal_orange" : "text-white"}`}>
                      {display}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Pipeline — highlight non-defaults */}
          <div>
            <p className="text-xs text-terminal_gray mb-1">Pipeline</p>
            <div className="space-y-1">
              {Object.entries(pipeline).map(([key, values]) => {
                if (!values || values.length === 0) return null;
                const nonDefault = isPipelineNonDefault(key, values);

                let display;
                if (values.length === 2) display = "both";
                else display = values[0] ? "on" : "off";

                return (
                  <div key={key} className="flex justify-between text-sm">
                    <span className="text-terminal_gray">{key}</span>
                    <span className={`font-mono ${
                      nonDefault
                        ? display === "both"
                          ? "text-terminal_orange"
                          : display === "off"
                            ? "text-terminal_red"
                            : "text-terminal_green"
                        : "text-white"
                    }`}>
                      {display}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

        </div>
      )}
    </aside>
  );
}
