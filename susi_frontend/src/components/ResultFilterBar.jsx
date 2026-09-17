// susi_frontend/src/components/ResultFilterBar.jsx

// ============================================================
// ResultFilterBar — Top section of Result Mode
//
// Dynamic filter bar for completed run results. All filter
// options are derived from the actual result data, not hardcoded.
//
// Props:
//   categories     — string[] of distinct categories in results
//   models         — string[] of distinct models in results
//   filters        — current filter state:
//                    { category, model, minScore, maxScore, sortBy, sortDir }
//   onFilterChange — callback(newFilters)
//   onExport       — callback() to export CSV
//   onCompare      — callback() to load into Compare Mode
//   onNewRun       — callback() to go back to ParameterMode
//   onDelete       — callback() to delete this run
//   runName        — string, displayed run name
//   totalResults   — number, total results before filtering
//   filteredCount  — number, results after filtering
// ============================================================

export default function ResultFilterBar({
  categories = [],
  models = [],
  filters = {},
  onFilterChange,
  onExport,
  onCompare,
  onNewRun,
  onDelete,
  runName = "",
  totalResults = 0,
  filteredCount = 0,
}) {
  const {
    category = "",
    model = "",
    minScore = "",
    maxScore = "",
    sortBy = "index",
    sortDir = "asc",
  } = filters;

  const update = (key, value) => {
    onFilterChange({ ...filters, [key]: value });
  };

  const sortOptions = [
    { value: "index", label: "Question #" },
    { value: "score", label: "Score" },
    { value: "bert_score", label: "BERT" },
    { value: "rouge_l", label: "ROUGE-L" },
    { value: "time", label: "Time" },
    { value: "tok_s", label: "tok/s" },
    { value: "kategorie", label: "Category" },
  ];

  return (
    <div className="shrink-0 bg-dark_background border-b border-terminal_gray/15 px-5 py-3 space-y-3">
      {/* Top row: Run name + action buttons */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold text-white">{runName}</h2>
          <span className="text-xs text-terminal_gray">
            {filteredCount === totalResults
              ? `${totalResults} results`
              : `${filteredCount} / ${totalResults} results`}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onExport}
            className="px-3 py-1.5 rounded text-xs text-terminal_gray
              border border-terminal_gray/20 hover:text-white hover:border-terminal_gray/40
              transition-colors"
            title="Export results as CSV"
          >
            📥 Export
          </button>
          <button
            onClick={onCompare}
            className="px-3 py-1.5 rounded text-xs text-primary_gold
              border border-primary_gold/30 hover:bg-primary_gold/10
              transition-colors"
            title="Compare with another run"
          >
            ⚔️ Compare
          </button>
          <button
            onClick={onNewRun}
            className="px-3 py-1.5 rounded text-xs text-terminal_gray
              border border-terminal_gray/20 hover:text-white hover:border-terminal_gray/40
              transition-colors"
          >
            + New run
          </button>
          <button
            onClick={onDelete}
            className="px-3 py-1.5 rounded text-xs text-terminal_red/60
              border border-terminal_red/20 hover:text-terminal_red hover:border-terminal_red/40
              transition-colors"
            title="Delete this run"
          >
            🗑️
          </button>
        </div>
      </div>

      {/* Filter row */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Category filter */}
        <div className="flex items-center gap-1.5">
          <label className="text-xs text-terminal_gray">Category</label>
          <select
            value={category}
            onChange={(e) => update("category", e.target.value)}
            className="px-2 py-1.5 rounded text-xs bg-surface_dark border border-terminal_gray/20
              text-white focus:outline-none focus:border-primary_gold appearance-none cursor-pointer"
          >
            <option value="">All</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>

        {/* Model filter */}
        {models.length > 1 && (
          <div className="flex items-center gap-1.5">
            <label className="text-xs text-terminal_gray">Model</label>
            <select
              value={model}
              onChange={(e) => update("model", e.target.value)}
              className="px-2 py-1.5 rounded text-xs bg-surface_dark border border-terminal_gray/20
                text-white focus:outline-none focus:border-primary_gold appearance-none cursor-pointer"
            >
              <option value="">All</option>
              {models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Score quick-filters */}
        <div className="flex items-center gap-1.5">
          <label className="text-xs text-terminal_gray">Score</label>
          <div className="flex gap-1">
            {[
              { label: "All", min: "", max: "" },
              { label: "Low ≤1", min: "0", max: "1" },
              { label: "Mid 2", min: "2", max: "2" },
              { label: "High 3", min: "3", max: "3" },
            ].map((preset) => {
              const isActive =
                String(minScore) === preset.min &&
                String(maxScore) === preset.max;
              return (
                <button
                  key={preset.label}
                  onClick={() => {
                    update("minScore", preset.min);
                    onFilterChange({
                      ...filters,
                      minScore: preset.min,
                      maxScore: preset.max,
                    });
                  }}
                  className={`
                    px-2 py-1 rounded text-xs transition-colors
                    ${
                      isActive
                        ? "bg-primary_gold text-dark_background font-semibold"
                        : "bg-surface_dark text-terminal_gray border border-terminal_gray/20 hover:border-primary_gold/40"
                    }
                  `}
                >
                  {preset.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Sort */}
        <div className="flex items-center gap-1.5 ml-auto">
          <label className="text-xs text-terminal_gray">Sort</label>
          <select
            value={sortBy}
            onChange={(e) => update("sortBy", e.target.value)}
            className="px-2 py-1.5 rounded text-xs bg-surface_dark border border-terminal_gray/20
              text-white focus:outline-none focus:border-primary_gold appearance-none cursor-pointer"
          >
            {sortOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <button
            onClick={() =>
              update("sortDir", sortDir === "asc" ? "desc" : "asc")
            }
            className="px-2 py-1.5 rounded text-xs bg-surface_dark border border-terminal_gray/20
              text-terminal_gray hover:text-white transition-colors"
          >
            {sortDir === "asc" ? "↑" : "↓"}
          </button>
        </div>
      </div>
    </div>
  );
}
