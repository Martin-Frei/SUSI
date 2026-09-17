// susi_frontend/src/components/QuestionPreviewModal.jsx


// ============================================================
// QuestionPreviewModal — Section 2b
//
// Modal overlay showing all questions from a question set in a
// read-only scrollable list. Closable via X button in the top
// right corner OR clicking the dark backdrop behind the modal.
//
// Fetches question details from getQuestionSetDetail(id) when
// opened. Shows question text, reference answer, and category.
//
// Props:
//   isOpen     — boolean, controls visibility
//   onClose    — callback to close the modal
//   questions  — array of question objects from getQuestionSetDetail()
//                [{ frage: "...", referenz: "...", kategorie: "..." }, ...]
//   setName    — name of the question set (shown in header)
//   loading    — boolean, true while fetching detail
// ============================================================

import { useEffect } from "react";

export default function QuestionPreviewModal({ isOpen, onClose, questions = [], setName = "", loading = false }) {

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === "Escape") onClose();
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [isOpen]);

  if (!isOpen) return null;

  // Color for category badges
  const categoryColor = (cat) => {
    const colors = {
      susi: "bg-primary_gold/20 text-primary_gold",
      technisch: "bg-terminal_orange/20 text-terminal_orange",
      technik: "bg-terminal_orange/20 text-terminal_orange",
      persoenlich: "bg-blue-500/20 text-blue-400",
      datum: "bg-terminal_green/20 text-terminal_green",
      lernen: "bg-purple-500/20 text-purple-400",
      projekte: "bg-cyan-500/20 text-cyan-400",
    };
    return colors[cat?.toLowerCase()] || "bg-terminal_gray/20 text-terminal_gray";
  };

  return (
    // Backdrop — click to close
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      {/* Modal container — stop click propagation so clicking inside doesn't close */}
      <div
        className="relative w-full max-w-2xl max-h-[80vh] mx-4 rounded-lg
          bg-dark_background border border-terminal_gray/30 shadow-2xl
          flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-terminal_gray/20">
          <div>
            <h2 className="text-base font-semibold text-white">{setName}</h2>
            <p className="text-xs text-terminal_gray mt-0.5">
              {questions.length} questions — read only
            </p>
          </div>

          {/* X close button */}
          <button
            onClick={onClose}
            className="p-1.5 rounded text-terminal_gray hover:text-white
              hover:bg-surface_dark transition-colors"
            title="Close (Esc)"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Scrollable question list */}
        <div className="flex-1 overflow-y-auto px-5 py-3 space-y-3">
          {loading ? (
            <p className="text-sm text-terminal_gray animate-pulse py-8 text-center">
              Loading questions…
            </p>
          ) : questions.length === 0 ? (
            <p className="text-sm text-terminal_red py-8 text-center">
              No questions in this set
            </p>
          ) : (
            questions.map((q, idx) => (
              <div
                key={idx}
                className="rounded p-3 bg-surface_dark border border-terminal_gray/10 space-y-1.5"
              >
                {/* Question number + category */}
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono text-terminal_gray">
                    Q{idx + 1}
                  </span>
                  {q.kategorie && (
                    <span className={`text-xs px-2 py-0.5 rounded-full ${categoryColor(q.kategorie)}`}>
                      {q.kategorie}
                    </span>
                  )}
                </div>

                {/* Question text */}
                <p className="text-sm text-white">{q.frage}</p>

                {/* Reference answer */}
                {q.referenz && (
                  <p className="text-xs text-terminal_gray border-l-2 border-terminal_gray/30 pl-2">
                    {q.referenz}
                  </p>
                )}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-terminal_gray/20 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded text-sm
              bg-surface_dark text-terminal_gray border border-terminal_gray/20
              hover:text-white hover:border-terminal_gray/40 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}