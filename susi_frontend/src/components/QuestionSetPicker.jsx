// susi_frontend/src/components/QuestionSetPicker.jsx


// ============================================================
// QuestionSetPicker — Section 2 of ConfigSidebar
//
// Dropdown to select a question set from GET /questionsets/.
// Shows name + question count. A small preview icon opens
// QuestionPreviewModal with the full question list.
//
// Props:
//   questionSets       — array from getQuestionSets()
//                        [{ id: 1, name: "Datumsarithmetik", question_count: 10 }, ...]
//   selectedId         — currently selected question set id (number | null)
//   onChange           — callback(newId: number)
//   onPreviewClick     — callback(id: number) — opens the preview modal
//   loading            — boolean, true while fetching
// ============================================================

export default function QuestionSetPicker({ questionSets = [], selectedId = null, onChange, onPreviewClick, loading = false }) {

  if (loading) {
    return (
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-terminal_txt_gold uppercase tracking-wide">
          Question Set
        </h3>
        <p className="text-sm text-terminal_gray animate-pulse">Loading sets…</p>
      </div>
    );
  }

  const selectedSet = questionSets.find((qs) => qs.id === selectedId);

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-terminal_txt_gold uppercase tracking-wide">
        Question Set
      </h3>

      <div className="flex items-center gap-2">
        {/* Dropdown */}
        <select
          value={selectedId ?? ""}
          onChange={(e) => {
            const val = e.target.value;
            onChange(val ? Number(val) : null);
          }}
          className="flex-1 px-3 py-2 rounded text-sm
            bg-surface_dark border border-terminal_gray/20 text-white
            focus:outline-none focus:border-primary_gold
            appearance-none cursor-pointer"
        >
          <option value="" disabled>Select question set…</option>
          {questionSets.map((qs) => (
            <option key={qs.id} value={qs.id}>
              {qs.name} ({qs.question_count} questions)
            </option>
          ))}
        </select>

        {/* Preview button — only visible when a set is selected */}
        {selectedId && (
          <button
            onClick={() => onPreviewClick(selectedId)}
            className="p-2 rounded border border-terminal_gray/20
              text-terminal_gray hover:text-primary_gold hover:border-primary_gold/40
              transition-colors duration-150 shrink-0"
            title="Preview questions"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          </button>
        )}
      </div>

      {/* Question count + type info */}
      {selectedSet && (
        <p className="text-xs text-terminal_gray">
          {selectedSet.question_count} questions
          {selectedSet.description && ` — ${selectedSet.description}`}
        </p>
      )}

      {!selectedId && questionSets.length > 0 && (
        <p className="text-xs text-terminal_orange">Select a question set</p>
      )}

      {questionSets.length === 0 && !loading && (
        <p className="text-xs text-terminal_red">No question sets found — upload one first</p>
      )}
    </div>
  );
}