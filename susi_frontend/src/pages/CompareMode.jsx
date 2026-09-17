// susi_frontend/src/pages/CompareMode.jsx


// ============================================================
// CompareMode — Page (State 4)
//
// Compare up to 3 runs side-by-side. Runs must share the same
// question set. Parameters are filtered to the intersection —
// only values present in ALL selected runs are selectable.
//
// Layout:
//   Top:    Run selectors (A, B, optional C) + parameter filters
//   Middle: Summary cards + filter chips
//   Bottom: Comparison table (one row per question, columns per run)
//
// Props:
//   initialRunIdA — pre-selected Run A (from Result Mode)
//   initialRunIdB — pre-selected Run B (optional)
//   onNewRun       — callback() to go back to ParameterMode
// ============================================================

import { useState, useEffect, useMemo } from "react";
import { getRuns, getRunResults } from "../../services/api";

// --- Score badge helper --------------------------------------

const scoreBadge = (score) => {
  if (score == null) return { bg: "bg-terminal_gray/20", text: "text-terminal_gray", label: "—" };
  if (score >= 3) return { bg: "bg-terminal_green/15", text: "text-terminal_green", label: score };
  if (score >= 2) return { bg: "bg-terminal_green/10", text: "text-terminal_green/70", label: score };
  if (score >= 1) return { bg: "bg-terminal_orange/15", text: "text-terminal_orange", label: score };
  return { bg: "bg-terminal_red/15", text: "text-terminal_red", label: score };
};

const deltaColor = (d) => {
  if (d > 0) return "text-terminal_green";
  if (d < 0) return "text-terminal_red";
  return "text-terminal_gray";
};

const deltaLabel = (d) => {
  if (d > 0) return `+${d}`;
  if (d === 0) return "=";
  return String(d);
};

// --- Run color assignments -----------------------------------

const RUN_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"];
const RUN_LABELS = ["A", "B", "C"];

export default function CompareMode({ initialRunIdA = null, initialRunIdB = null, onNewRun }) {

  // --- State --------------------------------------------------

  const [allRuns, setAllRuns] = useState([]);
  const [loading, setLoading] = useState(true);

  const [selectedRunIds, setSelectedRunIds] = useState([
    initialRunIdA,
    initialRunIdB,
    null,
  ]);

  const [runResults, setRunResults] = useState({});
  const [selectedParams, setSelectedParams] = useState({});
  const [filter, setFilter] = useState("all");
  const [expandedRow, setExpandedRow] = useState(null);

  // --- Load all runs on mount --------------------------------

  useEffect(() => {
    async function load() {
      try {
        const runs = await getRuns();
        setAllRuns(Array.isArray(runs) ? runs : runs.runs || []);
      } catch (err) {
        console.error("Failed to load runs:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // --- Load results when a run is selected -------------------

  useEffect(() => {
    selectedRunIds.forEach(async (runId) => {
      if (!runId || runResults[runId]) return;

      try {
        const results = await getRunResults(runId);
        const data = Array.isArray(results) ? results : results.results || [];
        setRunResults((prev) => ({ ...prev, [runId]: data }));
      } catch (err) {
        console.error(`Failed to load results for run ${runId}:`, err);
      }
    });
  }, [selectedRunIds]);

  // --- Derive question set filter for run selectors ----------

  const activeRunIds = selectedRunIds.filter(Boolean);
  const firstRun = allRuns.find((r) => r.id === selectedRunIds[0]);
  const questionSetId = firstRun?.question_set_id;

  const compatibleRuns = useMemo(() => {
    if (!questionSetId) return allRuns;
    return allRuns.filter((r) => r.question_set_id === questionSetId);
  }, [allRuns, questionSetId]);

  // --- Compute parameter intersection across selected runs ---

  const parameterOptions = useMemo(() => {
    const options = {};

    activeRunIds.forEach((runId) => {
      const results = runResults[runId] || [];
      results.forEach((r) => {
        if (r.model) {
          if (!options.model) options.model = {};
          if (!options.model[r.model]) options.model[r.model] = new Set();
          options.model[r.model].add(runId);
        }
        if (r.params) {
          Object.entries(r.params).forEach(([key, value]) => {
            if (!options[key]) options[key] = {};
            const strVal = String(value);
            if (!options[key][strVal]) options[key][strVal] = new Set();
            options[key][strVal].add(runId);
          });
        }
      });
    });

    const result = {};
    Object.entries(options).forEach(([param, values]) => {
      result[param] = {};
      Object.entries(values).forEach(([value, runSet]) => {
        result[param][value] = {
          inAll: activeRunIds.every((id) => runSet.has(id)),
          missingIn: activeRunIds.filter((id) => !runSet.has(id)),
        };
      });
    });

    return result;
  }, [activeRunIds, runResults]);

  // --- Auto-select first available value for each param ------

  useEffect(() => {
    const newSelected = { ...selectedParams };
    let changed = false;
    Object.entries(parameterOptions).forEach(([param, values]) => {
      if (!newSelected[param]) {
        const firstAvailable = Object.entries(values).find(([_, info]) => info.inAll);
        if (firstAvailable) {
          newSelected[param] = firstAvailable[0];
          changed = true;
        }
      }
    });
    if (changed) setSelectedParams(newSelected);
  }, [parameterOptions]);

  // --- Filter results by selected parameters -----------------

  const filteredResultsPerRun = useMemo(() => {
    const perRun = {};

    activeRunIds.forEach((runId) => {
      const results = runResults[runId] || [];
      perRun[runId] = results.filter((r) => {
        if (selectedParams.model && r.model !== selectedParams.model) return false;
        if (r.params) {
          for (const [key, value] of Object.entries(selectedParams)) {
            if (key === "model") continue;
            if (r.params[key] != null && String(r.params[key]) !== value) return false;
          }
        }
        return true;
      });
    });

    return perRun;
  }, [activeRunIds, runResults, selectedParams]);

  // --- Build comparison rows ---------------------------------

  const comparisonRows = useMemo(() => {
    if (activeRunIds.length < 2) return [];

    const runAResults = filteredResultsPerRun[activeRunIds[0]] || [];

    return runAResults.map((baseResult) => {
      const row = {
        index: baseResult.index,
        question: baseResult.question,
        kategorie: baseResult.kategorie,
        runs: {},
        deltas: {},
      };

      activeRunIds.forEach((runId) => {
        const results = filteredResultsPerRun[runId] || [];
        row.runs[runId] = results.find((r) =>
          r.question === baseResult.question || r.index === baseResult.index
        ) || null;
      });

      const baseScore = row.runs[activeRunIds[0]]?.score;
      activeRunIds.slice(1).forEach((runId) => {
        const score = row.runs[runId]?.score;
        row.deltas[runId] = (baseScore != null && score != null) ? score - baseScore : null;
      });

      return row;
    });
  }, [activeRunIds, filteredResultsPerRun]);

  // --- Apply view filter -------------------------------------

  const visibleRows = useMemo(() => {
    if (filter === "all") return comparisonRows;
    return comparisonRows.filter((row) => {
      const deltas = Object.values(row.deltas).filter((d) => d != null);
      if (filter === "regressions") return deltas.some((d) => d < 0);
      if (filter === "improvements") return deltas.some((d) => d > 0);
      return true;
    });
  }, [comparisonRows, filter]);

  // --- Summary -----------------------------------------------

  const summary = useMemo(() => {
    const summaries = {};
    activeRunIds.slice(1).forEach((runId) => {
      let wins = 0, losses = 0, ties = 0;
      comparisonRows.forEach((row) => {
        const d = row.deltas[runId];
        if (d == null) return;
        if (d > 0) wins++;
        else if (d < 0) losses++;
        else ties++;
      });
      summaries[runId] = { wins, losses, ties };
    });
    return summaries;
  }, [activeRunIds, comparisonRows]);

  // --- Run selector handler ----------------------------------

  const handleRunSelect = (slot, runId) => {
    const newIds = [...selectedRunIds];
    newIds[slot] = runId ? Number(runId) : null;
    setSelectedRunIds(newIds);
    setSelectedParams({});
  };

  // --- Loading -----------------------------------------------

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-terminal_gray animate-pulse">
        Loading runs…
      </div>
    );
  }

  // --- Render ------------------------------------------------

  return (
    <div className="flex flex-col h-full overflow-hidden">

      {/* Top: Run selectors + parameter filters */}
      <div className="shrink-0 px-5 py-4 border-b border-terminal_gray/15 space-y-3">

        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Compare Runs</h2>
          <button
            onClick={onNewRun}
            className="px-3 py-1.5 rounded text-xs text-terminal_gray
              border border-terminal_gray/20 hover:text-white transition-colors"
          >
            ← Back
          </button>
        </div>

        {/* Run dropdowns */}
        <div className="flex gap-3">
          {[0, 1, 2].map((slot) => (
            <div key={slot} className="flex-1">
              <label className="text-xs text-terminal_gray block mb-1">
                <span
                  className="inline-block w-3 h-3 rounded-sm mr-1"
                  style={{ backgroundColor: RUN_COLORS[slot] }}
                />
                {slot === 0 ? "Baseline" : `Challenger ${RUN_LABELS[slot]}`}
                {slot === 2 ? " (optional)" : ""}
              </label>
              <select
                value={selectedRunIds[slot] ?? ""}
                onChange={(e) => handleRunSelect(slot, e.target.value)}
                className="w-full px-3 py-2 rounded text-xs bg-surface_dark border border-terminal_gray/20
                  text-white focus:outline-none focus:border-primary_gold appearance-none cursor-pointer"
              >
                <option value="">
                  {slot === 0 ? "Select baseline…" : slot === 2 ? "None" : "Select run…"}
                </option>
                {(slot === 0 ? allRuns : compatibleRuns).map((run) => (
                  <option
                    key={run.id}
                    value={run.id}
                    disabled={selectedRunIds.includes(run.id)}
                  >
                    {run.name || `Run #${run.id}`} — {run.status}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>

        {/* Parameter intersection filters */}
        {Object.keys(parameterOptions).length > 0 && (
          <div className="flex flex-wrap gap-4">
            {Object.entries(parameterOptions).map(([param, values]) => (
              <div key={param} className="space-y-1">
                <label className="text-xs text-terminal_gray">{param}</label>
                <div className="flex gap-1">
                  {Object.entries(values).map(([value, info]) => (
                    <button
                      key={value}
                      onClick={() => info.inAll && setSelectedParams((p) => ({ ...p, [param]: value }))}
                      disabled={!info.inAll}
                      title={
                        info.inAll
                          ? value
                          : `Missing in: ${info.missingIn.map((id) => {
                              const run = allRuns.find((r) => r.id === id);
                              return run?.name || `#${id}`;
                            }).join(", ")}`
                      }
                      className={`
                        px-2 py-1 rounded text-xs font-mono transition-colors
                        ${!info.inAll
                          ? "bg-terminal_gray/5 text-terminal_gray/30 cursor-not-allowed line-through"
                          : selectedParams[param] === value
                            ? "bg-primary_gold text-dark_background font-semibold"
                            : "bg-surface_dark text-terminal_gray border border-terminal_gray/20 hover:border-primary_gold/40"
                        }
                      `}
                    >
                      {param === "model" ? value.split(":")[0] : value}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Need at least 2 runs */}
      {activeRunIds.length < 2 ? (
        <div className="flex-1 flex items-center justify-center text-terminal_gray/40 text-sm">
          Select at least two runs to compare
        </div>
      ) : (
        <>
          {/* Summary cards */}
          <div className="shrink-0 flex gap-3 px-5 py-3 border-b border-terminal_gray/15">
            {activeRunIds.map((runId, i) => {
              const results = filteredResultsPerRun[runId] || [];
              const scores = results.map((r) => r.score).filter((s) => s != null);
              const avg = scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
              const toks = results.map((r) => r.tok_s).filter((t) => t != null);
              const avgTok = toks.length > 0 ? toks.reduce((a, b) => a + b, 0) / toks.length : 0;
              const run = allRuns.find((r) => r.id === runId);

              return (
                <div key={runId} className="flex-1 rounded px-3 py-2 bg-surface_dark border border-terminal_gray/10">
                  <div className="flex items-center gap-1.5 mb-1">
                    <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: RUN_COLORS[i] }} />
                    <p className="text-xs text-terminal_gray truncate">{RUN_LABELS[i]}: {run?.name || `#${runId}`}</p>
                  </div>
                  <div className="flex items-baseline gap-3">
                    <p className="text-lg font-mono font-semibold text-white">{avg.toFixed(2)}</p>
                    <p className="text-xs font-mono text-primary_gold">{avgTok.toFixed(1)} tok/s</p>
                  </div>
                </div>
              );
            })}

            {Object.entries(summary).map(([runId, s]) => {
              const idx = activeRunIds.indexOf(Number(runId));
              return (
                <div key={`sum-${runId}`} className="flex-1 rounded px-3 py-2 bg-surface_dark border border-terminal_gray/10">
                  <p className="text-xs text-terminal_gray mb-1">{RUN_LABELS[idx]} vs A</p>
                  <div className="flex gap-2 text-sm font-mono">
                    <span className="text-terminal_green">↑{s.wins}</span>
                    <span className="text-terminal_red">↓{s.losses}</span>
                    <span className="text-terminal_gray">={s.ties}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Filter chips */}
          <div className="shrink-0 flex items-center gap-2 px-5 py-2 border-b border-terminal_gray/15">
            {[
              { key: "all", label: "All" },
              { key: "regressions", label: "📉 Regressions" },
              { key: "improvements", label: "🚀 Improvements" },
            ].map((f) => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={`
                  px-3 py-1 rounded text-xs transition-colors
                  ${filter === f.key
                    ? "bg-primary_gold text-dark_background font-semibold"
                    : "bg-surface_dark text-terminal_gray border border-terminal_gray/20"
                  }
                `}
              >
                {f.label}
              </button>
            ))}
            <span className="ml-auto text-xs text-terminal_gray">
              {visibleRows.length}/{comparisonRows.length} questions
            </span>
          </div>

          {/* Comparison table */}
          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-terminal_gray/15 sticky top-0 bg-dark_background z-10">
                  <th className="text-left py-2 px-3 text-terminal_gray font-medium w-8">#</th>
                  <th className="text-left py-2 px-3 text-terminal_gray font-medium">Question</th>
                  <th className="text-left py-2 px-3 text-terminal_gray font-medium w-16">Cat</th>
                  {activeRunIds.map((runId, i) => (
                    <th key={runId} className="text-center py-2 px-3 font-medium w-16"
                      style={{ color: RUN_COLORS[i] }}>
                      {RUN_LABELS[i]}
                    </th>
                  ))}
                  {activeRunIds.slice(1).map((runId, i) => (
                    <th key={`d-${runId}`} className="text-center py-2 px-3 text-terminal_gray font-medium w-12">
                      Δ{RUN_LABELS[i + 1]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((row, idx) => {
                  const isExpanded = expandedRow === idx;
                  return (
                    <tbody key={idx}>
                      <tr
                        onClick={() => setExpandedRow(isExpanded ? null : idx)}
                        className={`cursor-pointer transition-colors ${isExpanded ? "bg-surface_dark" : "hover:bg-surface_dark/50"}`}
                      >
                        <td className="py-2 px-3 text-terminal_gray font-mono">{row.index}</td>
                        <td className="py-2 px-3 text-white truncate max-w-[250px]" title={row.question}>{row.question}</td>
                        <td className="py-2 px-3 text-terminal_gray">{row.kategorie || "—"}</td>
                        {activeRunIds.map((runId) => {
                          const badge = scoreBadge(row.runs[runId]?.score);
                          return (
                            <td key={runId} className="py-2 px-3 text-center">
                              <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${badge.bg} ${badge.text}`}>
                                {badge.label}
                              </span>
                            </td>
                          );
                        })}
                        {activeRunIds.slice(1).map((runId) => {
                          const d = row.deltas[runId];
                          return (
                            <td key={`d-${runId}`} className={`py-2 px-3 text-center font-mono font-semibold ${deltaColor(d)}`}>
                              {d != null ? deltaLabel(d) : "—"}
                            </td>
                          );
                        })}
                      </tr>

                      {isExpanded && (
                        <tr>
                          <td colSpan={99} className="px-3 py-3 bg-surface_dark border-b border-terminal_gray/10">
                            <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${activeRunIds.length}, 1fr)` }}>
                              {activeRunIds.map((runId, i) => {
                                const result = row.runs[runId];
                                return (
                                  <div key={runId}>
                                    <div className="flex items-center gap-1.5 mb-1">
                                      <span className="w-2 h-2 rounded-sm" style={{ backgroundColor: RUN_COLORS[i] }} />
                                      <span className="text-xs text-terminal_gray">Run {RUN_LABELS[i]}</span>
                                    </div>
                                    <p className="text-sm text-white bg-dark_background rounded p-2 whitespace-pre-wrap min-h-[60px]">
                                      {result?.answer || "—"}
                                    </p>
                                    <div className="flex gap-3 mt-1 text-xs text-terminal_gray">
                                      {result?.bert_score != null && <span>BERT: {result.bert_score.toFixed(2)}</span>}
                                      {result?.rouge_l != null && <span>ROUGE: {result.rouge_l.toFixed(2)}</span>}
                                      {result?.time != null && <span>{result.time.toFixed(1)}s</span>}
                                      {result?.tok_s != null && <span>{result.tok_s.toFixed(1)} tok/s</span>}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                            <div className="mt-3">
                              <p className="text-xs text-terminal_gray mb-1">Reference</p>
                              <p className="text-sm text-terminal_green/80 bg-dark_background rounded p-2 whitespace-pre-wrap">
                                {row.runs[activeRunIds[0]]?.referenz || "—"}
                              </p>
                            </div>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  );
                })}
              </tbody>
            </table>

            {visibleRows.length === 0 && (
              <div className="flex items-center justify-center h-32 text-terminal_gray/40 text-sm">
                No questions match the current filter
              </div>
            )}
          </div>

          {/* Bottom summary */}
          <div className="shrink-0 px-5 py-2 border-t border-terminal_gray/15 text-xs text-terminal_gray text-center">
            {Object.entries(summary).map(([runId, s], i) => {
              const idx = activeRunIds.indexOf(Number(runId));
              return (
                <span key={runId}>
                  {i > 0 ? " · " : ""}
                  {RUN_LABELS[idx]} vs A: wins {s.wins}, loses {s.losses}, tied {s.ties}
                </span>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}