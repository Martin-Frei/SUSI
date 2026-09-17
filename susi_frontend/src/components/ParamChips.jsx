// susi_frontend/src/components/ParamChips.jsx


// ============================================================
// ParamChips — Section 4 of ConfigSidebar
//
// Renders clickable chip groups for each RAG parameter.
// Numeric params (top_k, temperature, num_ctx) have preset
// chips + a [+] button for custom values.
// system_prompt is a multi-select chip group from the yaml.
// thinking is a 3-way toggle (On / Off / Both).
//
// Clicking a chip toggles it. Multiple chips = grid run.
// Default chips are pre-selected (filled).
//
// Props:
//   params   — current state object, e.g.:
//              { top_k: [7], temperature: [0.0], num_ctx: [4096],
//                system_prompt: ["praezise_neu"], thinking: [false] }
//   onChange — callback(newParams) — full params object
// ============================================================

import { useState } from "react";

// --- Preset definitions with defaults marked -----------------

const CHIP_GROUPS = [
  {
    key: "top_k",
    label: "top_k",
    presets: [3, 5, 7, 9],
    defaultValue: 7,
    type: "number",
    step: 1,
    min: 1,
    max: 20,
  },
  {
    key: "temperature",
    label: "Temperature",
    presets: [0.0, 0.1, 0.3, 0.5],
    defaultValue: 0.0,
    type: "number",
    step: 0.1,
    min: 0.0,
    max: 2.0,
  },
  {
    key: "num_ctx",
    label: "num_ctx",
    presets: [2048, 4096, 8192],
    defaultValue: 4096,
    type: "number",
    step: 1024,
    min: 512,
    max: 32768,
  },
];

const PROMPT_OPTIONS = ["praezise_neu", "praezise_hybrid", "detailed"];
const PROMPT_DEFAULT = "praezise_neu";

// --- Reusable chip group for numeric params ------------------

function NumericChipGroup({ config, selectedValues, onToggle, onAddCustom }) {
  const [showInput, setShowInput] = useState(false);
  const [customValue, setCustomValue] = useState("");

  const handleAddCustom = () => {
    const parsed = parseFloat(customValue);
    if (isNaN(parsed)) return;

    // Don't add duplicates
    const allValues = [...config.presets, ...selectedValues];
    if (!allValues.includes(parsed)) {
      onAddCustom(parsed);
    } else if (!selectedValues.includes(parsed)) {
      onToggle(parsed);
    }
    setCustomValue("");
    setShowInput(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") handleAddCustom();
    if (e.key === "Escape") {
      setShowInput(false);
      setCustomValue("");
    }
  };

  // Merge presets + any custom values already selected
  const allChips = [...new Set([...config.presets, ...selectedValues])].sort((a, b) => a - b);

  return (
    <div className="space-y-1.5">
      <span className="text-xs text-terminal_gray">{config.label}</span>
      <div className="flex flex-wrap gap-1.5 items-center">
        {allChips.map((value) => {
          const isSelected = selectedValues.includes(value);
          const isDefault = value === config.defaultValue;

          return (
            <button
              key={value}
              onClick={() => onToggle(value)}
              className={`
                px-2.5 py-1 rounded text-xs font-mono transition-colors duration-150
                ${isSelected
                  ? "bg-primary_gold text-dark_background font-semibold"
                  : "bg-surface_dark text-terminal_gray border border-terminal_gray/20 hover:border-primary_gold/40"
                }
                ${isDefault && !isSelected ? "ring-1 ring-primary_gold/30" : ""}
              `}
              title={isDefault ? `Default: ${value}` : `${value}`}
            >
              {config.type === "number" && Number.isInteger(value) ? value : value.toFixed(1)}
            </button>
          );
        })}

        {/* Custom value input */}
        {showInput ? (
          <input
            type="number"
            value={customValue}
            onChange={(e) => setCustomValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={() => {
              if (customValue === "") setShowInput(false);
            }}
            step={config.step}
            min={config.min}
            max={config.max}
            autoFocus
            className="w-16 px-2 py-1 rounded text-xs font-mono
              bg-dark_background border border-primary_gold/40 text-white
              focus:outline-none focus:border-primary_gold"
            placeholder={config.step < 1 ? "0.0" : "0"}
          />
        ) : (
          <button
            onClick={() => setShowInput(true)}
            className="px-2 py-1 rounded text-xs text-terminal_gray
              border border-dashed border-terminal_gray/30
              hover:border-primary_gold/50 hover:text-primary_gold transition-colors"
            title="Add custom value"
          >
            +
          </button>
        )}
      </div>
    </div>
  );
}

// --- System prompt multi-select chips ------------------------

function PromptChips({ selectedPrompts, onToggle }) {
  return (
    <div className="space-y-1.5">
      <span className="text-xs text-terminal_gray">System Prompt</span>
      <div className="flex flex-wrap gap-1.5">
        {PROMPT_OPTIONS.map((prompt) => {
          const isSelected = selectedPrompts.includes(prompt);
          const isDefault = prompt === PROMPT_DEFAULT;

          return (
            <button
              key={prompt}
              onClick={() => onToggle(prompt)}
              className={`
                px-2.5 py-1 rounded text-xs transition-colors duration-150
                ${isSelected
                  ? "bg-primary_gold text-dark_background font-semibold"
                  : "bg-surface_dark text-terminal_gray border border-terminal_gray/20 hover:border-primary_gold/40"
                }
                ${isDefault && !isSelected ? "ring-1 ring-primary_gold/30" : ""}
              `}
            >
              {prompt}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// --- Thinking 3-way toggle (On / Off / Both) -----------------

function ThinkingToggle({ values, onChange }) {
  // values: [false] = Off, [true] = On, [true, false] = Both
  const current =
    values.length === 2 ? "both" : values[0] === true ? "on" : "off";

  const handleClick = (mode) => {
    if (mode === "on") onChange([true]);
    else if (mode === "off") onChange([false]);
    else onChange([true, false]);
  };

  const options = [
    { key: "on", label: "On" },
    { key: "off", label: "Off" },
    { key: "both", label: "Both" },
  ];

  return (
    <div className="space-y-1.5">
      <span className="text-xs text-terminal_gray">Thinking</span>
      <div className="flex rounded overflow-hidden border border-terminal_gray/20">
        {options.map((opt) => (
          <button
            key={opt.key}
            onClick={() => handleClick(opt.key)}
            className={`
              flex-1 px-3 py-1.5 text-xs font-medium transition-colors duration-150
              ${current === opt.key
                ? "bg-primary_gold text-dark_background"
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

// --- Main component ------------------------------------------

export default function ParamChips({ params, onChange }) {

  // Toggle a numeric value: add if missing, remove if present.
  // At least one value must remain selected.
  const toggleNumeric = (key, value) => {
    const current = params[key] || [];
    let next;

    if (current.includes(value)) {
      next = current.filter((v) => v !== value);
      if (next.length === 0) return; // prevent empty selection
    } else {
      next = [...current, value].sort((a, b) => a - b);
    }

    onChange({ ...params, [key]: next });
  };

  // Add a custom value that's not in presets
  const addCustom = (key, value) => {
    const current = params[key] || [];
    onChange({ ...params, [key]: [...current, value].sort((a, b) => a - b) });
  };

  // Toggle a prompt option
  const togglePrompt = (prompt) => {
    const current = params.system_prompt || [PROMPT_DEFAULT];
    let next;

    if (current.includes(prompt)) {
      next = current.filter((p) => p !== prompt);
      if (next.length === 0) return;
    } else {
      next = [...current, prompt];
    }

    onChange({ ...params, system_prompt: next });
  };

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-terminal_txt_gold uppercase tracking-wide">
        Parameters
      </h3>

      {CHIP_GROUPS.map((config) => (
        <NumericChipGroup
          key={config.key}
          config={config}
          selectedValues={params[config.key] || [config.defaultValue]}
          onToggle={(value) => toggleNumeric(config.key, value)}
          onAddCustom={(value) => addCustom(config.key, value)}
        />
      ))}

      <PromptChips
        selectedPrompts={params.system_prompt || [PROMPT_DEFAULT]}
        onToggle={togglePrompt}
      />

      <ThinkingToggle
        values={params.thinking || [false]}
        onChange={(values) => onChange({ ...params, thinking: values })}
      />
    </div>
  );
}