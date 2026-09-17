// susi_frontend/src/components/ResultDetailModal.jsx


// ============================================================
// ResultDetailModal — Detail inspector in Result Mode
//
// Full-screen slide-over showing deep analysis of a single
// question result. Opened from ResultTable via "Full detail view".
// Closable via X, backdrop click, or Escape.
//
// Shows:
//   - Answer vs. Reference (side by side)
//   - All metrics: Score, BERT, ROUGE-L, Time, tok/s
//   - Router profile + rewritten query
//   - Retrieved sources (chunks — text in V2)
//   - Combination / model info
//
// Props:
//   isOpen   — boolean
//   onClose  — callback()
//   result   — single result object with all fields
// ============================================================

import { useEffect } from "react";

const scoreBadge = (score) => {
  if (score == null) return { bg: "bg-terminal_gray/20", text: "text-terminal_gray", label: "—" };
  if (score >= 3) return { bg: "bg-terminal_green/15", text: "text-terminal_green", label: score };
  if (score >= 2) return { bg: "bg-terminal_green/10", text: "text-terminal_green/70", label: score };
  if (score >= 1) return { bg: "bg-terminal_orange/15", text: "text-terminal_orange", label: score };
  if (score === 6) return { bg: "bg-yellow-500/15", text: "text-yellow-400", label: "VC" };
  return { bg: "bg-terminal_red/15", text: "text-terminal_red", label: score };
};

export default function ResultDetailModal({ isOpen, onClose, result }) {

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [isOpen, onClose]);

  // Prevent body scroll
  useEffect(() => {
    if (isOpen) document.body.style.overflow = "hidden";
    else document.body.style.overflow = "";
    return () => { document.body.style.overflow = ""; };
  }, [isOpen]);

  if (!isOpen || !result) return null;

  const badge = scoreBadge(result.score);
  const r = result;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      {/* Slide-over panel */}
      <div
        className="w-full max-w-2xl h-full bg-dark_background border-l border-terminal_gray/30
          shadow-2xl overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 bg-dark_background border-b border-terminal_gray/20 px-6 py-4">
          <div className="flex items-start justify-between">
            <div className="flex-1 pr-4">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-mono text-terminal_gray">Q{r.index}</span>
                <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${badge.bg} ${badge.text}`}>
                  Score {badge.label}
                </span>
                {r.kategorie && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-primary_gold/15 text-primary_gold">
                    {r.kategorie}
                  </span>
                )}
              </div>
              <h2 className="text-base font-medium text-white">{r.question}</h2>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded text-terminal_gray hover:text-white hover:bg-surface_dark transition-colors shrink-0"
              title="Close (Esc)"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
                fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>

        <div className="px-6 py-4 space-y-6">

          {/* Metrics row */}
          <div className="grid grid-cols-5 gap-2">
            {[
              { label: "Score", value: r.score ?? "—", color: badge.text },
              { label: "BERT", value: r.bert_score?.toFixed(3) ?? "—", color: "text-white" },
              { label: "ROUGE-L", value: r.rouge_l?.toFixed(3) ?? "—", color: "text-white" },
              { label: "Time", value: r.time != null ? `${r.time.toFixed(1)}s` : "—", color: "text-white" },
              { label: "tok/s", value: r.tok_s?.toFixed(1) ?? "—", color: "text-primary_gold" },
            ].map((m) => (
              <div key={m.label} className="rounded px-3 py-2 bg-surface_dark border border-terminal_gray/10 text-center">
                <p className="text-xs text-terminal_gray">{m.label}</p>
                <p className={`text-base font-mono font-semibold ${m.color}`}>{m.value}</p>
              </div>
            ))}
          </div>

          {/* Answer vs Reference */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h3 className="text-xs font-medium text-terminal_gray mb-2 uppercase tracking-wide">Answer</h3>
              <div className="bg-surface_dark rounded-lg p-4 text-sm text-white whitespace-pre-wrap leading-relaxed min-h-[100px]">
                {r.answer || "—"}
              </div>
            </div>
            <div>
              <h3 className="text-xs font-medium text-terminal_gray mb-2 uppercase tracking-wide">Reference</h3>
              <div className="bg-surface_dark rounded-lg p-4 text-sm text-terminal_green/80 whitespace-pre-wrap leading-relaxed min-h-[100px]">
                {r.referenz || "—"}
              </div>
            </div>
          </div>

          {/* Pipeline info */}
          <div>
            <h3 className="text-xs font-medium text-terminal_gray mb-2 uppercase tracking-wide">Pipeline</h3>
            <div className="bg-surface_dark rounded-lg p-4 space-y-2">
              <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
                {r.model && (
                  <>
                    <span className="text-terminal_gray">Model</span>
                    <span className="text-white font-mono">{r.model}</span>
                  </>
                )}
                {r.router_profil && (
                  <>
                    <span className="text-terminal_gray">Router profile</span>
                    <span className="text-primary_gold font-mono">{r.router_profil}</span>
                  </>
                )}
                {r.combination && (
                  <>
                    <span className="text-terminal_gray">Combination</span>
                    <span className="text-white font-mono">{r.combination}</span>
                  </>
                )}
                {r.rewritten_query && (
                  <>
                    <span className="text-terminal_gray">Rewritten query</span>
                    <span className="text-white">{r.rewritten_query}</span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Sources */}
          {r.sources && r.sources.length > 0 && (
            <div>
              <h3 className="text-xs font-medium text-terminal_gray mb-2 uppercase tracking-wide">
                Sources ({r.sources.length})
              </h3>
              <div className="space-y-1.5">
                {r.sources.map((src, i) => {
                  const isAgent = src.includes("agent_datum") || src.includes("agent_pedia");
                  return (
                    <div
                      key={i}
                      className={`
                        flex items-center gap-2 px-3 py-2 rounded text-sm
                        ${isAgent
                          ? "bg-primary_gold/10 border border-primary_gold/20"
                          : "bg-surface_dark border border-terminal_gray/10"
                        }
                      `}
                    >
                      <span className="text-xs shrink-0">
                        {isAgent ? "🧮" : "📄"}
                      </span>
                      <span className={`font-mono text-xs ${isAgent ? "text-primary_gold" : "text-terminal_gray"}`}>
                        {src}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Chunks — V2 placeholder */}
          <div>
            <h3 className="text-xs font-medium text-terminal_gray mb-2 uppercase tracking-wide">
              Retrieved chunks
            </h3>
            <div className="rounded-lg border border-dashed border-terminal_gray/20 p-4 text-center">
              <p className="text-xs text-terminal_gray/40">
                Chunk text and reranker scores — coming in V2
              </p>
            </div>
          </div>

          {/* Raw params if available */}
          {r.params && Object.keys(r.params).length > 0 && (
            <div>
              <h3 className="text-xs font-medium text-terminal_gray mb-2 uppercase tracking-wide">
                Parameters
              </h3>
              <div className="bg-surface_dark rounded-lg p-4">
                <pre className="text-xs font-mono text-terminal_gray whitespace-pre-wrap">
                  {JSON.stringify(r.params, null, 2)}
                </pre>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}