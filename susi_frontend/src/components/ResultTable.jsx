// susi_frontend/src/components/ResultTable.jsx


// ============================================================
// ResultTable — Central drill-down table in Result Mode
//
// Sortable table listing all questions with scores, metrics,
// and timing. Rows are expandable — click to show answer vs.
// reference, retrieved chunks, router profile, and rewritten query.
//
// Props:
//   results    — filtered + sorted array of result objects
//   onRowClick — callback(result) to open detail modal (optional)
// ============================================================

import { useState, Fragment } from "react";

// Score badge color
const scoreBadge = (score) => {
  if (score == null) return { bg: "bg-terminal_gray/20", text: "text-terminal_gray", label: "—" };
  if (score >= 3) return { bg: "bg-terminal_green/15", text: "text-terminal_green", label: score };
  if (score >= 2) return { bg: "bg-terminal_green/10", text: "text-terminal_green/70", label: score };
  if (score >= 1) return { bg: "bg-terminal_orange/15", text: "text-terminal_orange", label: score };
  if (score === 6) return { bg: "bg-yellow-500/15", text: "text-yellow-400", label: "VC" };
  return { bg: "bg-terminal_red/15", text: "text-terminal_red", label: score };
};

export default function ResultTable({ results = [], onRowClick }) {
  const [expandedIndex, setExpandedIndex] = useState(null);

  const toggleExpand = (idx) => {
    setExpandedIndex(expandedIndex === idx ? null : idx);
  };

  if (results.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-terminal_gray/40 text-sm">
        No results match your filters
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">

        {/* Header */}
        <thead>
          <tr className="border-b border-terminal_gray/15">
            <th className="text-left py-2 px-3 text-terminal_gray font-medium w-8">#</th>
            <th className="text-left py-2 px-3 text-terminal_gray font-medium">Question</th>
            <th className="text-left py-2 px-3 text-terminal_gray font-medium w-20">Category</th>
            <th className="text-center py-2 px-3 text-terminal_gray font-medium w-14">Score</th>
            <th className="text-center py-2 px-3 text-terminal_gray font-medium w-14">BERT</th>
            <th className="text-center py-2 px-3 text-terminal_gray font-medium w-16">ROUGE</th>
            <th className="text-right py-2 px-3 text-terminal_gray font-medium w-14">Time</th>
            <th className="text-right py-2 px-3 text-terminal_gray font-medium w-14">tok/s</th>
            <th className="text-center py-2 px-3 text-terminal_gray font-medium w-14">Agent</th>
            <th className="text-left py-2 px-3 text-terminal_gray font-medium w-28">Model</th>
          </tr>
        </thead>

        <tbody>
          {results.map((r, idx) => {
            const badge = scoreBadge(r.score);
            const isExpanded = expandedIndex === idx;
            const hasAgent = r.sources?.some((s) =>
              s.includes("agent_datum") || s.includes("agent_pedia")
            );

            return (
              <Fragment key={`${r.index}-${idx}`}>
                {/* Main row */}
                <tr
                  onClick={() => toggleExpand(idx)}
                  className={`
                    cursor-pointer transition-colors
                    ${isExpanded
                      ? "bg-surface_dark"
                      : "hover:bg-surface_dark/50"
                    }
                  `}
                >
                  <td className="py-2 px-3 text-terminal_gray font-mono">{r.index}</td>
                  <td className="py-2 px-3 text-white truncate max-w-[300px]" title={r.question}>
                    {r.question}
                  </td>
                  <td className="py-2 px-3 text-terminal_gray">{r.kategorie || "—"}</td>
                  <td className="py-2 px-3 text-center">
                    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${badge.bg} ${badge.text}`}>
                      {badge.label}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-center text-terminal_gray font-mono">
                    {r.bert_score != null ? r.bert_score.toFixed(2) : "—"}
                  </td>
                  <td className="py-2 px-3 text-center text-terminal_gray font-mono">
                    {r.rouge_l != null ? r.rouge_l.toFixed(2) : "—"}
                  </td>
                  <td className="py-2 px-3 text-right text-terminal_gray font-mono">
                    {r.time != null ? `${r.time.toFixed(1)}s` : "—"}
                  </td>
                  <td className="py-2 px-3 text-right text-terminal_gray font-mono">
                    {r.tok_s != null ? r.tok_s.toFixed(1) : "—"}
                  </td>
                  <td className="py-2 px-3 text-center">
                    {hasAgent ? "🧮" : ""}
                  </td>
                  <td className="py-2 px-3 text-terminal_gray font-mono truncate max-w-[120px]">
                    {r.model ? r.model.split(":")[0] : "—"}
                  </td>
                </tr>

                {/* Expanded detail row */}
                {isExpanded && (
                  <tr>
                    <td colSpan={10} className="px-3 py-3 bg-surface_dark border-b border-terminal_gray/10">
                      <div className="space-y-3 max-w-4xl">

                        {/* Answer vs Reference */}
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <p className="text-xs text-terminal_gray mb-1">Answer</p>
                            <p className="text-sm text-white bg-dark_background rounded p-2 whitespace-pre-wrap">
                              {r.answer || "—"}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs text-terminal_gray mb-1">Reference</p>
                            <p className="text-sm text-terminal_green/80 bg-dark_background rounded p-2 whitespace-pre-wrap">
                              {r.referenz || "—"}
                            </p>
                          </div>
                        </div>

                        {/* Metadata row */}
                        <div className="flex gap-4 text-xs text-terminal_gray flex-wrap">
                          {r.router_profil && (
                            <span>Router: <span className="text-primary_gold">{r.router_profil}</span></span>
                          )}
                          {r.rewritten_query && (
                            <span>Rewritten: <span className="text-white">{r.rewritten_query}</span></span>
                          )}
                          {r.model && (
                            <span>Model: <span className="text-white">{r.model}</span></span>
                          )}
                          {r.combination && (
                            <span>Combo: <span className="text-white">{r.combination}</span></span>
                          )}
                        </div>

                        {/* Sources */}
                        {r.sources && r.sources.length > 0 && (
                          <div>
                            <p className="text-xs text-terminal_gray mb-1">Sources</p>
                            <div className="flex gap-1.5 flex-wrap">
                              {r.sources.map((src, si) => (
                                <span
                                  key={si}
                                  className="px-2 py-0.5 rounded text-xs bg-dark_background text-terminal_gray border border-terminal_gray/15"
                                >
                                  {src}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Detail button */}
                        {onRowClick && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onRowClick(r);
                            }}
                            className="text-xs text-primary_gold hover:underline"
                          >
                            🔍 Full detail view
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}