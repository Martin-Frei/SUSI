//susi_frontend/src/pages/ResultMode.jsx


// ============================================================
// ResultMode — Page (State 3)
//
// Full analysis view for a completed/aborted/failed run.
// Loads all results via getRunResults(), applies client-side
// filtering and sorting, displays charts and drill-down table.
//
// Layout:
//   Top:    ResultFilterBar (full width)
//   Middle: ResultCharts (reuses LiveCharts logic but complete + clickable)
//   Bottom: ResultTable (sortable, expandable)
//
// Props:
//   runId    — completed run ID
//   onCompare — callback(runIdA, runIdB) to open CompareMode
//   onNewRun  — callback() to go back to ParameterMode
// ============================================================

import { useState, useEffect, useMemo } from "react";
import ResultFilterBar from "../components/ResultFilterBar";
import ResultTable from "../components/ResultTable";
import ResultDetailModal from "../components/ResultDetailModal";
import LiveCharts from "../components/LiveCharts";
import { getRunResults, getRunStatus, deleteRun } from "../../services/api";

export default function ResultMode({ runId, onCompare, onNewRun }) {

  // --- State --------------------------------------------------

  const [allResults, setAllResults] = useState([]);
  const [runInfo, setRunInfo] = useState({ name: "", config: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [filters, setFilters] = useState({
    category: "",
    model: "",
    minScore: "",
    maxScore: "",
    sortBy: "index",
    sortDir: "asc",
  });

  const [detailResult, setDetailResult] = useState(null);

  // --- Load results on mount ---------------------------------

  useEffect(() => {
    async function loadResults() {
      setLoading(true);
      try {
        const [results, status] = await Promise.all([
          getRunResults(runId),
          getRunStatus(runId),
        ]);

        setAllResults(results);
        setRunInfo({
          name: status.name || `Run #${runId}`,
          config: {
            models: status.models || [],
            params: status.params || {},
            pipeline: status.pipeline || {},
          },
        });
      } catch (err) {
        setError(err.message);
        console.error("Failed to load results:", err);
      } finally {
        setLoading(false);
      }
    }

    loadResults();
  }, [runId]);

  // --- Derived: distinct categories and models ----------------

  const categories = useMemo(() => {
    return [...new Set(allResults.map((r) => r.kategorie).filter(Boolean))].sort();
  }, [allResults]);

  const models = useMemo(() => {
    return [...new Set(allResults.map((r) => r.model).filter(Boolean))];
  }, [allResults]);

  // --- Apply filters and sorting -----------------------------

  const filteredResults = useMemo(() => {
    let filtered = [...allResults];

    // Category filter
    if (filters.category) {
      filtered = filtered.filter((r) => r.kategorie === filters.category);
    }

    // Model filter
    if (filters.model) {
      filtered = filtered.filter((r) => r.model === filters.model);
    }

    // Score filter
    if (filters.minScore !== "") {
      filtered = filtered.filter((r) => r.score >= Number(filters.minScore));
    }
    if (filters.maxScore !== "") {
      filtered = filtered.filter((r) => r.score <= Number(filters.maxScore));
    }

    // Sort
    const { sortBy, sortDir } = filters;
    filtered.sort((a, b) => {
      let aVal = a[sortBy];
      let bVal = b[sortBy];

      // Handle nulls
      if (aVal == null) aVal = sortDir === "asc" ? Infinity : -Infinity;
      if (bVal == null) bVal = sortDir === "asc" ? Infinity : -Infinity;

      // String comparison for category
      if (typeof aVal === "string") {
        return sortDir === "asc"
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }

      return sortDir === "asc" ? aVal - bVal : bVal - aVal;
    });

    return filtered;
  }, [allResults, filters]);

  // --- Summary stats -----------------------------------------

  const stats = useMemo(() => {
    if (filteredResults.length === 0) return null;

    const scores = filteredResults.map((r) => r.score).filter((s) => s != null);
    const berts = filteredResults.map((r) => r.bert_score).filter((s) => s != null);
    const times = filteredResults.map((r) => r.time).filter((t) => t != null);
    const toks = filteredResults.map((r) => r.tok_s).filter((t) => t != null);

    const avg = (arr) => arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;

    return {
      avgScore: avg(scores).toFixed(2),
      avgBert: avg(berts).toFixed(3),
      avgTime: avg(times).toFixed(1),
      avgTokS: avg(toks).toFixed(1),
      accuracy: scores.length > 0
        ? ((scores.filter((s) => s >= 2).length / scores.length) * 100).toFixed(1)
        : "0",
    };
  }, [filteredResults]);

  // --- CSV export --------------------------------------------

  const handleExport = () => {
    if (filteredResults.length === 0) return;

    const headers = ["index", "question", "kategorie", "score", "bert_score", "rouge_l", "time", "tok_s", "model", "router_profil", "answer", "referenz"];
    const rows = filteredResults.map((r) =>
      headers.map((h) => {
        const val = r[h];
        if (val == null) return "";
        const str = String(val);
        return str.includes(",") || str.includes('"') || str.includes("\n")
          ? `"${str.replace(/"/g, '""')}"`
          : str;
      }).join(",")
    );

    const csv = [headers.join(","), ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${runInfo.name || "results"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // --- Delete handler ----------------------------------------

  const handleDelete = async () => {
    if (!confirm(`Delete "${runInfo.name}" and all results?`)) return;
    try {
      await deleteRun(runId);
      onNewRun();
    } catch (err) {
      console.error("Delete failed:", err);
    }
  };

  // --- Compare handler ---------------------------------------

  const handleCompare = () => {
    onCompare(runId, null);
  };

  // --- Loading / Error states --------------------------------

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-terminal_gray animate-pulse">
        Loading results…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-6">
        <p className="text-terminal_red mb-4">{error}</p>
        <button onClick={onNewRun} className="text-sm text-terminal_gray underline">
          ← Back to config
        </button>
      </div>
    );
  }

  // --- Render -------------------------------------------------

  return (
    <div className="flex flex-col h-full">

      {/* Top: Filter bar */}
      <ResultFilterBar
        categories={categories}
        models={models}
        filters={filters}
        onFilterChange={setFilters}
        onExport={handleExport}
        onCompare={handleCompare}
        onNewRun={onNewRun}
        onDelete={handleDelete}
        runName={runInfo.name}
        totalResults={allResults.length}
        filteredCount={filteredResults.length}
      />

      {/* Summary stats */}
      {stats && (
        <div className="shrink-0 flex gap-3 px-5 py-3 border-b border-terminal_gray/15">
          <div className="flex-1 rounded px-3 py-2 bg-surface_dark border border-terminal_gray/10">
            <p className="text-xs text-terminal_gray">Accuracy</p>
            <p className="text-lg font-mono font-semibold text-terminal_green">{stats.accuracy}%</p>
          </div>
          <div className="flex-1 rounded px-3 py-2 bg-surface_dark border border-terminal_gray/10">
            <p className="text-xs text-terminal_gray">Avg score</p>
            <p className="text-lg font-mono font-semibold text-white">{stats.avgScore}</p>
          </div>
          <div className="flex-1 rounded px-3 py-2 bg-surface_dark border border-terminal_gray/10">
            <p className="text-xs text-terminal_gray">Avg BERT</p>
            <p className="text-lg font-mono font-semibold text-white">{stats.avgBert}</p>
          </div>
          <div className="flex-1 rounded px-3 py-2 bg-surface_dark border border-terminal_gray/10">
            <p className="text-xs text-terminal_gray">Avg time</p>
            <p className="text-lg font-mono font-semibold text-white">{stats.avgTime}s</p>
          </div>
          <div className="flex-1 rounded px-3 py-2 bg-surface_dark border border-terminal_gray/10">
            <p className="text-xs text-terminal_gray">Avg tok/s</p>
            <p className="text-lg font-mono font-semibold text-primary_gold">{stats.avgTokS}</p>
          </div>
        </div>
      )}

      {/* Middle: Charts — reuse LiveCharts with full data */}
      <div className="shrink-0 max-h-[40vh] overflow-y-auto border-b border-terminal_gray/15">
        <LiveCharts
          results={filteredResults}
          gridConfig={runInfo.config}
        />
      </div>

      {/* Bottom: Drill-down table */}
      <div className="flex-1 overflow-y-auto">
        <ResultTable
          results={filteredResults}
          onRowClick={(result) => setDetailResult(result)}
        />
      </div>

      {/* Detail modal */}
      <ResultDetailModal
        isOpen={detailResult !== null}
        onClose={() => setDetailResult(null)}
        result={detailResult}
      />
    </div>
  );
}