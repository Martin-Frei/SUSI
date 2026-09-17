//susi_frontend/src/components/ModelSelector.jsx

// ============================================================
// ModelSelector — Section 3 of ConfigSidebar
//
// Renders checkboxes for all available Ollama models (fetched
// from GET /models/). Embedding models are already filtered
// out in api.js. Shows model name + size in GB.
//
// Props:
//   models          — array of model objects from getModels()
//                     [{ name: "qwen2.5-coder:7b", size: 4700000000 }, ...]
//   selectedModels  — array of selected model name strings
//   onChange         — callback(newSelectedModels: string[])
//   loading         — boolean, true while fetching from API
// ============================================================

export default function ModelSelector({ models = [], selectedModels = [], onChange, loading = false }) {

  const toggleModel = (modelName) => {
    if (selectedModels.includes(modelName)) {
      onChange(selectedModels.filter((m) => m !== modelName));
    } else {
      onChange([...selectedModels, modelName]);
    }
  };

  // Format bytes to human-readable GB string: 4700000000 → "4.7 GB"
  const formatSize = (model) => `${model.size_gb} GB`;

  if (loading) {
    return (
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-terminal_txt_gold uppercase tracking-wide">
          Models
        </h3>
        <p className="text-sm text-terminal_gray animate-pulse">Loading models…</p>
      </div>
    );
  }

  if (models.length === 0) {
    return (
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-terminal_txt_gold uppercase tracking-wide">
          Models
        </h3>
        <p className="text-sm text-terminal_red">No models found — is Ollama running?</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-terminal_txt_gold uppercase tracking-wide">
        Models
      </h3>

      <div className="space-y-1">
        {models.map((model) => {
          const isSelected = selectedModels.includes(model.name);

          return (
            <label
              key={model.name}
              className={`
                flex items-center gap-3 px-3 py-2 rounded cursor-pointer
                transition-colors duration-150
                ${isSelected
                  ? "bg-primary_gold/15 border border-primary_gold/40"
                  : "bg-surface_dark border border-transparent hover:border-terminal_gray/30"
                }
              `}
            >
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => toggleModel(model.name)}
                className="accent-primary_gold w-4 h-4 shrink-0"
              />
              <span className="text-sm text-white truncate">{model.name}</span>
              <span className="text-xs text-terminal_gray ml-auto shrink-0">
                {formatSize(model)}
              </span>
            </label>
          );
        })}
      </div>

      {selectedModels.length === 0 && (
        <p className="text-xs text-terminal_orange">Select at least one model</p>
      )}
    </div>
  );
}