//  susi_frontend/src/components/ConfigSidebar.jsx



// ============================================================
// ConfigSidebar — Left panel of Parameter Mode
//
// Assembles all 7 config sections into a scrollable sidebar:
// 1. Run name (text input)
// 2. Question set picker + preview
// 3. Model selector
// 4. Parameter chips
// 5. Pipeline toggles
// 6. Grid preview
// 7. Start button
//
// All state lives in ParameterMode and flows down as props.
// ConfigSidebar is a layout wrapper — no local state except
// the preview modal open/close.
//
// Props:
//   runName / onRunNameChange
//   questionSets / selectedQuestionSetId / onQuestionSetChange / questionSetLoading
//   questionDetail / questionDetailLoading
//   models / selectedModels / onModelsChange / modelsLoading
//   params / onParamsChange
//   pipeline / onPipelineChange
//   questionCount — for grid preview
//   onStart — callback to start the run
//   canStart — boolean, enables/disables start button
//   starting — boolean, true while POST is in flight
// ============================================================

import { useState } from "react";
import QuestionSetPicker from "./QuestionSetPicker";
import QuestionPreviewModal from "./QuestionPreviewModal";
import ModelSelector from "./ModelSelector";
import ParamChips from "./ParamChips";
import PipelineToggles from "./PipelineToggles";
import GridPreview from "./GridPreview";

export default function ConfigSidebar({
  runName,
  onRunNameChange,
  questionSets,
  selectedQuestionSetId,
  onQuestionSetChange,
  questionSetLoading,
  questionDetail,
  questionDetailLoading,
  onPreviewRequest,
  models,
  selectedModels,
  onModelsChange,
  modelsLoading,
  params,
  onParamsChange,
  pipeline,
  onPipelineChange,
  questionCount,
  onStart,
  canStart,
  starting,
}) {
  const [previewOpen, setPreviewOpen] = useState(false);

  const handlePreviewClick = (id) => {
    onPreviewRequest(id);
    setPreviewOpen(true);
  };

  return (
    <>
      <aside className="w-72 shrink-0 h-full overflow-y-auto border-r border-terminal_gray/15 bg-dark_background">
        <div className="p-4 space-y-6">

          {/* Section 1 — Run Name */}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-terminal_txt_gold uppercase tracking-wide">
              Run Name
            </h3>
            <input
              type="text"
              value={runName}
              onChange={(e) => onRunNameChange(e.target.value)}
              placeholder="Auto-generated if empty"
              className="w-full px-3 py-2 rounded text-sm
                bg-surface_dark border border-terminal_gray/20 text-white
                placeholder:text-terminal_gray/50
                focus:outline-none focus:border-primary_gold"
            />
          </div>

          {/* Section 2 — Question Set */}
          <QuestionSetPicker
            questionSets={questionSets}
            selectedId={selectedQuestionSetId}
            onChange={onQuestionSetChange}
            onPreviewClick={handlePreviewClick}
            loading={questionSetLoading}
          />

          {/* Section 3 — Models */}
          <ModelSelector
            models={models}
            selectedModels={selectedModels}
            onChange={onModelsChange}
            loading={modelsLoading}
          />

          {/* Section 4 — Parameters */}
          <ParamChips
            params={params}
            onChange={onParamsChange}
          />

          {/* Section 5 — Pipeline Toggles */}
          <PipelineToggles
            pipeline={pipeline}
            onChange={onPipelineChange}
          />

          {/* Section 6 — Grid Preview */}
          <GridPreview
            selectedModels={selectedModels}
            params={params}
            pipeline={pipeline}
            questionCount={questionCount}
          />

          {/* Section 7 — Start Button */}
          <button
            onClick={onStart}
            disabled={!canStart || starting}
            className={`
              w-full py-3 rounded text-sm font-semibold tracking-wide
              transition-colors duration-200
              ${canStart && !starting
                ? "bg-primary_gold text-dark_background hover:bg-primary_gold/90 cursor-pointer"
                : "bg-terminal_gray/20 text-terminal_gray cursor-not-allowed"
              }
            `}
          >
            {starting ? "Starting…" : "Start Evaluation"}
          </button>

        </div>
      </aside>

      {/* Question Preview Modal */}
      <QuestionPreviewModal
        isOpen={previewOpen}
        onClose={() => setPreviewOpen(false)}
        questions={questionDetail?.questions || []}
        setName={questionDetail?.name || ""}
        loading={questionDetailLoading}
      />
    </>
  );
}