//susi_frontend/src/components/LiveHeaderBar.jsx

// ============================================================
// LiveHeaderBar — Top section of Live Mode
//
// Shows real-time progress and timing metrics during an active
// evaluation run. Data comes from the status endpoint polled
// every 3 seconds in LiveMode.
//
// Layout: Progress bar (full width) → 4 KPI cards → Abort button
//
// Props:
//   runID         — active run ID (number)
//   runStatus     — "pending" | "running" | "completed" | "failed" | "aborted"
//   progressData  — { total: number, completed: number }
//   chartData     — array of result objects, each with .time (seconds)
//   onAbort       — callback() to abort the run
//   aborting      — boolean, true while abort POST is in flight
// ============================================================

import { useMemo } from "react";

export default function LiveHeaderBar({
  runID,
  runStatus = "pending",
  onAbort,
  aborting = false,
  progressData = {},
  chartData = [],
}) {
  const total = progressData.total || 0;
  const completed = progressData.completed || 0;
  const progress = total > 0 ? (completed / total) * 100 : 0;

  // --- Compute timing KPIs from chartData --------------------

  const timingStats = useMemo(() => {
    const times = chartData
      .map((item) => item.time)
      .filter((val) => typeof val === "number" && val > 0);

    const tokSec = chartData
      .map((item) => item.tok_s)
      .filter((val) => typeof val === "number" && val > 0);

    if (times.length === 0) {
      return { avg: 0, min: 0, max: 0, avgTokS: 0 };
    }

    return {
      avg: times.reduce((a, b) => a + b, 0) / times.length,
      min: Math.min(...times),
      max: Math.max(...times),
      avgTokS: tokSec.length > 0 ? tokSec.reduce((a, b) => a + b, 0) / tokSec.length : 0,
    };
  }, [chartData]);

  // --- Dynamic remaining time --------------------------------

  const remainingRuns = total - completed;
  const remainingSeconds = remainingRuns * timingStats.avg;

  // --- Format helper -----------------------------------------

  const formatTime = (seconds) => {
    if (seconds === 0) return "—";
    if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`;
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    if (seconds < 3600) {
      const min = Math.floor(seconds / 60);
      const sec = Math.floor(seconds % 60);
      return `${min}m ${sec}s`;
    }
    const hours = (seconds / 3600).toFixed(1);
    return `${hours}h`;
  };

  const isRunning = runStatus === "running" || runStatus === "pending";

  // --- KPI definitions ---------------------------------------

  const kpis = [
    {
      label: "Remaining",
      value: formatTime(remainingSeconds),
      color: remainingSeconds > 3600 ? "text-terminal_red" : "text-white",
    },
    {
      label: "Avg / Question",
      value: formatTime(timingStats.avg),
      color: "text-white",
    },
    {
      label: "Min",
      value: formatTime(timingStats.min),
      color: "text-terminal_green",
    },
    {
      label: "Max",
      value: formatTime(timingStats.max),
      color: "text-terminal_red",
    },
    {
      label: "⚡ tok/s",
      value: timingStats.avgTokS > 0 ? timingStats.avgTokS.toFixed(1) : "—",
      color: "text-primary_gold",
    },
  ];

  // --- Render ------------------------------------------------

  return (
    <div className="shrink-0 bg-dark_background border-b border-terminal_gray/15 px-5 py-3 space-y-3">

      {/* Run ID + Status label */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-mono text-terminal_gray">Run #{runID}</span>
          <span className={`
            text-xs px-2 py-0.5 rounded-full font-medium
            ${runStatus === "running"
              ? "bg-terminal_green/15 text-terminal_green"
              : runStatus === "pending"
                ? "bg-terminal_orange/15 text-terminal_orange"
                : runStatus === "failed"
                  ? "bg-terminal_red/15 text-terminal_red"
                  : "bg-terminal_gray/15 text-terminal_gray"
            }
          `}>
            {runStatus}
          </span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs">
          <span className="text-terminal_gray">
            {completed} / {total} completed
          </span>
          <span className="text-white font-mono font-semibold">
            {progress.toFixed(1)}%
          </span>
        </div>

        <div className="w-full h-2 rounded-full bg-surface_dark overflow-hidden">
          <div
            className="h-full rounded-full bg-primary_gold transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* KPI cards + Abort button */}
      <div className="flex items-center gap-3">

        {kpis.map((kpi) => (
          <div
            key={kpi.label}
            className="flex-1 rounded px-3 py-2 bg-surface_dark border border-terminal_gray/10"
          >
            <p className="text-xs text-terminal_gray">{kpi.label}</p>
            <p className={`text-lg font-mono font-semibold ${kpi.color}`}>
              {kpi.value}
            </p>
          </div>
        ))}

        {/* Abort button */}
        <button
          onClick={onAbort}
          disabled={!isRunning || aborting}
          className={`
            shrink-0 px-5 py-4 rounded text-sm font-semibold transition-colors duration-200
            ${isRunning && !aborting
              ? "bg-terminal_red/15 text-terminal_red border border-terminal_red/30 hover:bg-terminal_red/25 cursor-pointer"
              : "bg-terminal_gray/10 text-terminal_gray/40 border border-terminal_gray/10 cursor-not-allowed"
            }
          `}
        >
          {aborting ? "Aborting…" : "⛔ Abort"}
        </button>
      </div>
    </div>
  );
}