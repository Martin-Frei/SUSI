//susi_frontend/src/components/PipelineToggles.jsx


// ============================================================
// PipelineToggles — Section 5 of ConfigSidebar
//
// Renders a 3-way segmented toggle for each pipeline component:
// On / Off / Both. "Both" means the grid run tests both states
// (doubles the combinations for that toggle).
//
// Props:
//   pipeline — current state object, e.g.:
//              { reranker: [true], rewriter: [true], router: [true],
//                agent_datum: [true], agent_pedia: [false] }
//              [true]        = On
//              [false]       = Off
//              [true, false] = Both (grid)
//   onChange — callback(newPipeline) — full pipeline object
// ============================================================

const PIPELINE_COMPONENTS = [
  { key: "reranker",    label: "Reranker",    description: "Cross-encoder re-ranking of retrieved chunks",    defaultOn: true  },
  { key: "rewriter",    label: "Rewriter",    description: "Query reformulation & coreference resolution",    defaultOn: true  },
  { key: "router",      label: "Router",      description: "Automatic intent & category detection",          defaultOn: true  },
  { key: "agent_datum", label: "agent_datum",  description: "Deterministic date & calendar calculations",     defaultOn: true  },
  { key: "agent_pedia", label: "agent_pedia",  description: "External knowledge source (Britannica/Wikipedia)", defaultOn: false },
];

function ToggleRow({ config, values, onToggle }) {
  const current =
    values.length === 2 ? "both" : values[0] === true ? "on" : "off";

  const options = [
    { key: "on",   label: "On",   values: [true] },
    { key: "off",  label: "Off",  values: [false] },
    { key: "both", label: "Both", values: [true, false] },
  ];

  return (
    <div className="flex items-center gap-3">
      {/* Label — fixed width for alignment */}
      <span className="text-sm text-white w-28 shrink-0 truncate" title={config.description}>
        {config.label}
      </span>

      {/* 3-way segmented button */}
      <div className="flex rounded overflow-hidden border border-terminal_gray/20 flex-1">
        {options.map((opt) => (
          <button
            key={opt.key}
            onClick={() => onToggle(opt.values)}
            className={`
              flex-1 px-3 py-1.5 text-xs font-medium transition-colors duration-150
              ${current === opt.key
                ? opt.key === "both"
                  ? "bg-terminal_orange text-dark_background"
                  : opt.key === "on"
                    ? "bg-terminal_green text-dark_background"
                    : "bg-terminal_gray text-white"
                : "bg-surface_dark text-terminal_gray hover:text-white"
              }
            `}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function PipelineToggles({ pipeline, onChange }) {

  const handleToggle = (key, values) => {
    onChange({ ...pipeline, [key]: values });
  };

  // Count how many toggles are set to "Both" (doubles combinations)
  const bothCount = Object.values(pipeline).filter((v) => v.length === 2).length;

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-terminal_txt_gold uppercase tracking-wide">
        Pipeline
      </h3>

      <div className="space-y-2">
        {PIPELINE_COMPONENTS.map((config) => (
          <ToggleRow
            key={config.key}
            config={config}
            values={pipeline[config.key] || [config.defaultOn]}
            onToggle={(values) => handleToggle(config.key, values)}
          />
        ))}
      </div>

      {bothCount > 0 && (
        <p className="text-xs text-terminal_orange">
          {bothCount} toggle{bothCount > 1 ? "s" : ""} set to Both → ×{Math.pow(2, bothCount)} combinations
        </p>
      )}
    </div>
  );
}