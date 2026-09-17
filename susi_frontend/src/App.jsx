// ============================================================
// App — Root Component
//
// Manages the active dashboard mode and routes between:
//   1. ParameterMode  — configure and start a run (landing page)
//   2. LiveMode       — watch a running evaluation
//   3. ResultMode     — analyze a completed run
//   4. CompareMode    — compare two runs side by side
//
// Mode transitions:
//   Parameter → Start → Live → completed → Result → Compare
//   Any mode  → "New Run" → Parameter
//   Any mode  → select past run → Result
// ============================================================

import { useState } from "react";
import ParameterMode from "./pages/ParameterMode";
import LiveMode from "./pages/LiveMode";
import ResultMode from "./pages/ResultMode";
import CompareMode from "./pages/CompareMode";
import "./App.css";

const MODES = {
  PARAMETER: "parameter",
  LIVE: "live",
  RESULT: "result",
  COMPARE: "compare",
};

const MODE_LABELS = {
  [MODES.PARAMETER]: "Configure",
  [MODES.LIVE]: "Live",
  [MODES.RESULT]: "Results",
  [MODES.COMPARE]: "Compare",
};

export default function App() {
  const [mode, setMode] = useState(MODES.PARAMETER);
  const [activeRunId, setActiveRunId] = useState(null);
  const [compareRunIds, setCompareRunIds] = useState([null, null]);

  // --- Mode transition handlers --------------------------------

  const handleStartRun = (runId) => {
    setActiveRunId(runId);
    setMode(MODES.LIVE);
  };

  const handleRunCompleted = (runId) => {
    setActiveRunId(runId);
    setMode(MODES.RESULT);
  };

  const handleViewResult = (runId) => {
    setActiveRunId(runId);
    setMode(MODES.RESULT);
  };

  const handleCompare = (runIdA, runIdB) => {
    setCompareRunIds([runIdA, runIdB]);
    setMode(MODES.COMPARE);
  };

  const handleNewRun = () => {
    setActiveRunId(null);
    setMode(MODES.PARAMETER);
  };

  // --- Render --------------------------------------------------

  return (
    <div className="h-screen flex flex-col bg-dark_background text-white">

      {/* Top navigation bar */}
      <header className="shrink-0 flex items-center justify-between px-5 py-3 border-b border-terminal_gray/15">

        {/* Logo + title */}
        <div className="flex items-center gap-3">
          <span className="text-primary_gold font-bold text-lg tracking-tight">SUSI</span>
          <span className="text-terminal_gray text-sm">Eval Dashboard</span>
        </div>

        {/* Mode tabs */}
        <nav className="flex gap-1">
          {Object.entries(MODE_LABELS).map(([key, label]) => (
            <button
              key={key}
              onClick={() => {
                if (key === MODES.PARAMETER) handleNewRun();
                else if (key === MODES.RESULT && activeRunId) setMode(MODES.RESULT);
                else if (key === MODES.LIVE && activeRunId) setMode(MODES.LIVE);
              }}
              disabled={
                (key === MODES.LIVE && !activeRunId) ||
                (key === MODES.RESULT && !activeRunId) ||
                (key === MODES.COMPARE && !compareRunIds[0])
              }
              className={`
                px-4 py-1.5 rounded text-xs font-medium transition-colors duration-150
                ${mode === key
                  ? "bg-primary_gold text-dark_background"
                  : "text-terminal_gray hover:text-white disabled:text-terminal_gray/30 disabled:cursor-not-allowed"
                }
              `}
            >
              {label}
            </button>
          ))}
        </nav>

        {/* Run indicator */}
        <div className="text-xs text-terminal_gray min-w-[120px] text-right">
          {activeRunId ? (
            <span>
              Run <span className="text-white font-mono">#{activeRunId}</span>
              {mode === MODES.LIVE && (
                <span className="inline-block w-2 h-2 rounded-full bg-terminal_green ml-2 animate-pulse" />
              )}
            </span>
          ) : (
            <span className="text-terminal_gray/40">No active run</span>
          )}
        </div>
      </header>

      {/* Main content area */}
      <div className="flex-1 overflow-hidden">
        {mode === MODES.PARAMETER && (
          <ParameterMode onStartRun={handleStartRun} onViewResult={handleViewResult} />
        )}
        {mode === MODES.LIVE && (
          <LiveMode
            runId={activeRunId}
            onCompleted={handleRunCompleted}
            onNewRun={handleNewRun}
          />
        )}
        {mode === MODES.RESULT && (
          <ResultMode
            runId={activeRunId}
            onCompare={handleCompare}
            onNewRun={handleNewRun}
          />
        )}
        {mode === MODES.COMPARE && (
          <CompareMode
            initialRunIdA={compareRunIds[0]}
            initialRunIdB={compareRunIds[1]}
            onNewRun={handleNewRun}
          />
        )}
      </div>
    </div>
  );
}