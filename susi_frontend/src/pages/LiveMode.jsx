//susi_frontend/src/pages/LiveMode.jsx

// ============================================================
// LiveMode — Page (State 2)
//
// Assembles all live components: HeaderBar, Charts, Terminal,
// and the collapsible Parameter Sidebar. Runs pollRunStatus()
// on mount and distributes data to children.
//
// On completed → calls onCompleted to transition to ResultMode.
// On failed/aborted → shows error, keeps partial results.
//
// Layout discussion with Martin still open — current layout is
// a starting point that can be adjusted.
//
// Props:
//   runId       — active run ID
//   runConfig   — { name, models, params, pipeline, question_set_name, question_count }
//   onCompleted — callback(runId) when run finishes
//   onNewRun    — callback() to go back to ParameterMode
// ============================================================

import { useState, useEffect, useRef, useCallback } from "react";
import LiveHeaderBar from "../components/LiveHeaderBar";
import LiveCharts from "../components/LiveCharts";
import LiveTerminal from "../components/LiveTerminal";
import LiveParameterSidebar from "../components/LiveParameterSidebar";
import { getRunStatus, abortRun, formatDuration } from "../../services/api";

const POLL_INTERVAL = 3000;

export default function LiveMode({
  runId,
  runConfig = {},
  onCompleted,
  onNewRun,
}) {
  // --- State --------------------------------------------------

  const [status, setStatus] = useState({
    status: "pending",
    completed_runs: 0,
    total_runs: 0,
    current_question: "",
    current_model: "",
    current_combination: "",
    avg_response_time: 0,
    recent_results: [],
    error_message: null,
  });

  const [allResults, setAllResults] = useState([]);
  const [aborting, setAborting] = useState(false);
  const [error, setError] = useState(null);

  const seenIndexesRef = useRef(new Set());
  const timerRef = useRef(null);
  const stoppedRef = useRef(false);

  // --- Polling ------------------------------------------------

  const poll = useCallback(async () => {
    if (stoppedRef.current) return;

    try {
      const data = await getRunStatus(runId);
      setStatus(data);

      // Accumulate new results (deduplicate by index)
      if (data.recent_results && data.recent_results.length > 0) {
        setAllResults((prev) => {
          const newResults = data.recent_results.filter((r, idx) => {
            const uniquekey =
              r.index ?? `${r.question}_${r.model}-${prev.length + idx}`;
            if (seenIndexesRef.current.has(uniquekey)) {
              return false;
            }
            seenIndexesRef.current.add(uniquekey);
            return true;
          });
          return newResults.length > 0 ? [...prev, ...newResults] : prev;
        });
      }

      // Check terminal states
      if (data.status === "completed") {
        stoppedRef.current = true;
        setTimeout(() => onCompleted(runId), 1500);
        return;
      }

      if (data.status === "failed") {
        stoppedRef.current = true;
        setError(data.error_message || "Run failed");
        return;
      }

      if (data.status === "aborted") {
        stoppedRef.current = true;
        return;
      }
    } catch (err) {
      console.error("Polling error:", err);
    }

    if (!stoppedRef.current) {
      timerRef.current = setTimeout(poll, POLL_INTERVAL);
    }
  }, [runId, onCompleted]);

  useEffect(() => {
    stoppedRef.current = false;
    seenIndexesRef.current.clear();
    setAllResults([]);
    poll();

    return () => {
      stoppedRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [runId, poll]);

  // --- Abort handler ------------------------------------------

  const handleAbort = async () => {
    setAborting(true);
    try {
      await abortRun(runId);
    } catch (err) {
      console.error("Abort failed:", err);
    } finally {
      setAborting(false);
    }
  };

  // --- Prepare terminal data ---------------------------------

  const terminalData = allResults.map((r) => ({
    index: r.index,
    total: status.total_runs,
    question: r.question,
    score: r.score,
    time: r.time,
    router_profil: r.router_profil,
    model: r.model,
  }));

  // --- ETA calculation ----------------------------------------

  const remaining = status.total_runs - status.completed_runs;
  const avgTime = status.avg_response_time || 0;
  const eta =
    remaining > 0 && avgTime > 0 ? formatDuration(remaining * avgTime) : "";

  // --- Render -------------------------------------------------

  return (
    <div className="flex flex-col h-full relative">
      {/* Top: Header — full width */}
      <LiveHeaderBar
        runID={runId}
        runStatus={status.status}
        progressData={{
          total: status.total_runs,
          completed: status.completed_runs,
        }}
        chartData={allResults}
        onAbort={handleAbort}
        aborting={aborting}
      />

      {/* Status banners — full width */}
      {error && (
        <div className="shrink-0 mx-4 mt-3 px-4 py-3 rounded bg-terminal_red/10 border border-terminal_red/30">
          <p className="text-sm text-terminal_red">{error}</p>
        </div>
      )}

      {status.status === "completed" && (
        <div className="shrink-0 mx-4 mt-3 px-4 py-3 rounded bg-terminal_green/10 border border-terminal_green/30 flex items-center justify-between">
          <p className="text-sm text-terminal_green">
            Run completed — switching to results…
          </p>
        </div>
      )}

      {status.status === "aborted" && (
        <div className="shrink-0 mx-4 mt-3 px-4 py-3 rounded bg-terminal_orange/10 border border-terminal_orange/30 flex items-center justify-between">
          <p className="text-sm text-terminal_orange">
            Run aborted — {status.completed_runs}/{status.total_runs} results
            available
          </p>
          <button
            onClick={onNewRun}
            className="text-sm text-terminal_orange underline hover:text-white"
          >
            New run
          </button>
        </div>
      )}

      {/* Bottom: Charts (left 50%) + Terminal (right 50%) */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Charts — scrollable */}
        <div className="w-1/2 overflow-y-auto border-r border-terminal_gray/15">
          <LiveCharts results={allResults} gridConfig={runConfig} />
        </div>

        {/* Right: Terminal — full height */}
        <div className="w-1/2">
          <LiveTerminal
            terminalData={terminalData}
            currentModel={status.current_model}
            currentCombo={status.current_combination}
            eta={eta}
          />
        </div>
      </div>

      {/* Sidebar — overlays on top of charts when expanded */}
      <div className="absolute top-0 left-0 h-full z-20">
        <LiveParameterSidebar config={runConfig} />
      </div>
    </div>
  );
}
