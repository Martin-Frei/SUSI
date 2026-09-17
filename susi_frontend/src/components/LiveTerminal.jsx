// susi_frontend/src/components/LiveTerminal.jsx


// ============================================================
// LiveTerminal — Bottom section of Live Mode
//
// Scrollable terminal-style log feed showing one line per
// answered question. New lines arrive from the polling cycle
// in LiveMode (every 3s). LiveMode accumulates all results
// and passes them as terminalData.
//
// Features:
//   - Color-coded by score (green=3, orange=2, red=0-1)
//   - Auto-scroll toggle (on by default, pauses on manual scroll)
//   - Search/filter input to find specific questions
//   - Status bar: current model, current combination, ETA
//
// Props:
//   terminalData   — array of result objects, newest last:
//                    [{ index, total, question, score, time, router_profil, model }]
//   currentModel   — string, model currently being evaluated
//   currentCombo   — string, current parameter combination label
//   eta            — string, estimated time remaining (formatted)
// ============================================================

import { useState, useEffect, useRef, useCallback } from "react";

export default function LiveTerminal({
  terminalData = [],
  currentModel = "",
  currentCombo = "",
  eta = "",
}) {
  const [autoScroll, setAutoScroll] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const scrollRef = useRef(null);
  const userScrolledRef = useRef(false);

  // --- Auto-scroll on new data --------------------------------

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [terminalData, autoScroll]);

  // --- Pause auto-scroll on manual scroll up ------------------

  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 30;

    if (!isAtBottom && !userScrolledRef.current) {
      userScrolledRef.current = true;
      setAutoScroll(false);
    } else if (isAtBottom && userScrolledRef.current) {
      userScrolledRef.current = false;
      setAutoScroll(true);
    }
  }, []);

  // --- Filter lines by search query ---------------------------

  const filteredData = searchQuery
    ? terminalData.filter((line) =>
        line.question?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        line.router_profil?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        line.model?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : terminalData;

  // --- Score color coding ------------------------------------

  const scoreColor = (score) => {
    if (score >= 3) return "text-terminal_green";
    if (score >= 2) return "text-terminal_orange";
    return "text-terminal_red";
  };

  const scoreIcon = (score) => {
    if (score >= 3) return "✅";
    if (score >= 2) return "⚠️";
    return "❌";
  };

  // --- Format time -------------------------------------------

  const formatTime = (seconds) => {
    if (seconds == null) return "—";
    if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`;
    return `${seconds.toFixed(1)}s`;
  };

  // --- Render ------------------------------------------------

  return (
    <div className="flex flex-col bg-terminal_bg border-t border-terminal_gray/15 h-full">

      {/* Toolbar: search + auto-scroll toggle */}
      <div className="shrink-0 flex items-center gap-3 px-4 py-2 border-b border-terminal_gray/10">

        {/* Search input */}
        <div className="flex-1 relative">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter questions, models, profiles…"
            className="w-full pl-8 pr-3 py-1.5 rounded text-xs font-mono
              bg-dark_background border border-terminal_gray/20 text-white
              placeholder:text-terminal_gray/40
              focus:outline-none focus:border-primary_gold"
          />
          <svg
            xmlns="http://www.w3.org/2000/svg" width="14" height="14"
            viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            className="absolute left-2.5 top-1/2 -translate-y-1/2 text-terminal_gray/40"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </div>

        {/* Line count */}
        <span className="text-xs text-terminal_gray font-mono shrink-0">
          {filteredData.length}/{terminalData.length}
        </span>

        {/* Auto-scroll toggle */}
        <button
          onClick={() => {
            setAutoScroll(!autoScroll);
            userScrolledRef.current = false;
            if (!autoScroll && scrollRef.current) {
              scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
            }
          }}
          className={`
            shrink-0 px-3 py-1.5 rounded text-xs font-mono transition-colors
            ${autoScroll
              ? "bg-terminal_green/15 text-terminal_green border border-terminal_green/30"
              : "bg-surface_dark text-terminal_gray border border-terminal_gray/20 hover:text-white"
            }
          `}
          title={autoScroll ? "Auto-scroll ON — click to pause" : "Auto-scroll OFF — click to resume"}
        >
          {autoScroll ? "▼ Auto" : "▼ Paused"}
        </button>
      </div>

      {/* Log lines */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 py-2 font-mono text-xs leading-relaxed"
      >
        {filteredData.length === 0 && terminalData.length === 0 && (
          <p className="text-terminal_gray/40 py-4 text-center">
            Waiting for first result…
          </p>
        )}

        {filteredData.length === 0 && terminalData.length > 0 && (
          <p className="text-terminal_gray/40 py-4 text-center">
            No matches for "{searchQuery}"
          </p>
        )}

        {filteredData.map((line, idx) => (
          <div
            key={`${line.index}-${idx}`}
            className="flex items-baseline gap-2 py-0.5 hover:bg-surface_dark/50 px-1 -mx-1 rounded"
          >
            {/* Score icon */}
            <span className="shrink-0 w-5">{scoreIcon(line.score)}</span>

            {/* Question index */}
            <span className="text-terminal_gray shrink-0 w-16">
              Q{line.index}/{line.total}
            </span>

            {/* Question text (truncated) */}
            <span className="text-white truncate flex-1" title={line.question}>
              {line.question}
            </span>

            {/* Score */}
            <span className={`shrink-0 w-14 text-right font-semibold ${scoreColor(line.score)}`}>
              Score:{line.score}
            </span>

            {/* Response time */}
            <span className="shrink-0 w-14 text-right text-terminal_gray">
              {formatTime(line.time)}
            </span>

            {/* Router profile */}
            {line.router_profil && (
              <span className="shrink-0 text-primary_gold/70">
                {line.router_profil}
              </span>
            )}

            {/* Model (only show if multi-model run) */}
            {line.model && (
              <span className="shrink-0 text-terminal_gray/50 truncate max-w-[120px]">
                {line.model}
              </span>
            )}
          </div>
        ))}
      </div>

      {/* Status bar */}
      <div className="shrink-0 flex items-center justify-between px-4 py-1.5
        border-t border-terminal_gray/10 text-xs font-mono text-terminal_gray">
        <div className="flex items-center gap-4">
          {currentModel && (
            <span>
              Model: <span className="text-white">{currentModel}</span>
            </span>
          )}
          {currentCombo && (
            <span>
              Combo: <span className="text-white">{currentCombo}</span>
            </span>
          )}
        </div>
        {eta && (
          <span>
            ETA: <span className="text-terminal_orange">{eta}</span>
          </span>
        )}
      </div>
    </div>
  );
}