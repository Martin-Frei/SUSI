// susi_frontend/src/components/LiveCharts.jsx

// ============================================================
// LiveCharts — Center section of Live Mode
//
// Three chart types, all fed from the accumulated results
// that LiveMode collects via polling:
//
// 1. Parameter Boxplots (0–N charts)
//    One chart per parameter with multiple values in the grid.
//    Vertical boxplots (Q1, Median, Q3, Whiskers, Outliers).
//    Three tabs per chart: auto_score / BERT / ROUGE-L.
//
// 2. Category Boxplot (1 chart, always shown)
//    Horizontal boxplot, one box per question category.
//    Dynamic — new categories appear as results come in.
//    Same three tabs.
//
// 3. Response Time Scatter (1 chart, always shown)
//    X = question index, Y = seconds.
//    Dots colored by model, hoverable with full details.
//
// Props:
//   results   — accumulated array of all results so far:
//               [{ index, question, score, bert_score, rouge_l,
//                  time, model, kategorie, router_profil,
//                  combination, params: { top_k, temperature, ... } }]
//   gridConfig — { models: [...], params: { top_k: [5,7,9], ... },
//                  pipeline: { reranker: [true,false], ... } }
// ============================================================

import { useState, useEffect, useRef, useMemo } from "react";

// --- Color palette for models --------------------------------

const MODEL_COLORS = [
  "#2a78d6", "#eb6834", "#1baf7a", "#eda100",
  "#e87ba4", "#008300", "#6250d6", "#e34948",
];

const CATEGORY_COLORS = {
  susi: "#2a78d6",
  projekte: "#1baf7a",
  lernen: "#6250d6",
  persoenlich: "#eb6834",
  technik: "#eda100",
  datum: "#e87ba4",
  wissen: "#008300",
};

const DEFAULT_CAT_COLOR = "#73726c";

// --- Metric tab definitions ----------------------------------

const METRICS = [
  { key: "score", label: "auto_score", range: [0, 3] },
  { key: "bert_score", label: "BERT", range: [0, 1] },
  { key: "rouge_l", label: "ROUGE-L", range: [0, 1] },
];

// --- Boxplot statistics calculator ---------------------------

function calcBoxStats(values) {
  if (values.length === 0) return null;

  const sorted = [...values].sort((a, b) => a - b);
  const n = sorted.length;

  const q1Idx = Math.floor(n * 0.25);
  const q2Idx = Math.floor(n * 0.5);
  const q3Idx = Math.floor(n * 0.75);

  const q1 = sorted[q1Idx];
  const median = n % 2 === 0
    ? (sorted[q2Idx - 1] + sorted[q2Idx]) / 2
    : sorted[q2Idx];
  const q3 = sorted[q3Idx];
  const iqr = q3 - q1;

  const lowerFence = q1 - 1.5 * iqr;
  const upperFence = q3 + 1.5 * iqr;

  // Whiskers = last real data point inside fences
  const whiskerLow = sorted.find((v) => v >= lowerFence) ?? sorted[0];
  const whiskerHigh = [...sorted].reverse().find((v) => v <= upperFence) ?? sorted[n - 1];

  // Outliers = points outside fences
  const outliers = sorted.filter((v) => v < lowerFence || v > upperFence);

  return { q1, median, q3, iqr, whiskerLow, whiskerHigh, outliers, n };
}

// --- Metric Tabs component -----------------------------------

function MetricTabs({ activeMetric, onChange }) {
  return (
    <div className="flex gap-0.5 bg-dark_background rounded p-0.5">
      {METRICS.map((m) => (
        <button
          key={m.key}
          onClick={() => onChange(m.key)}
          className={`
            px-3 py-1 rounded text-xs font-medium transition-colors
            ${activeMetric === m.key
              ? "bg-surface_dark text-white"
              : "text-terminal_gray hover:text-white"
            }
          `}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}

// --- Vertical Boxplot (for parameters) -----------------------

function VerticalBoxplotChart({ title, labels, dataGroups, metricConfig }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    const ctx = canvasRef.current.getContext("2d");
    const canvas = canvasRef.current;
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.parentElement.clientWidth;
    const height = 220;

    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";
    ctx.scale(dpr, dpr);

    const pad = { top: 24, right: 20, bottom: 36, left: 44 };
    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;

    // Clear
    ctx.clearRect(0, 0, width, height);

    const [yMin, yMax] = metricConfig.range;
    const yScale = (v) => pad.top + plotH - ((v - yMin) / (yMax - yMin)) * plotH;

    // Grid lines
    const gridSteps = metricConfig.key === "score" ? [0, 1, 2, 3] : [0, 0.25, 0.5, 0.75, 1.0];
    ctx.strokeStyle = "rgba(102,102,102,0.15)";
    ctx.lineWidth = 0.5;
    ctx.font = "11px system-ui";
    ctx.fillStyle = "#666";
    ctx.textAlign = "right";

    gridSteps.forEach((v) => {
      if (v < yMin || v > yMax) return;
      const y = yScale(v);
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(width - pad.right, y);
      ctx.stroke();
      ctx.fillText(v % 1 === 0 ? v.toString() : v.toFixed(2), pad.left - 6, y + 4);
    });

    // Boxplots
    const boxWidth = Math.min(48, plotW / labels.length - 12);
    const gap = plotW / labels.length;

    labels.forEach((label, i) => {
      const stats = dataGroups[i];
      if (!stats) return;

      const cx = pad.left + gap * i + gap / 2;

      // Whisker line
      ctx.strokeStyle = "#888";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(cx, yScale(stats.whiskerHigh));
      ctx.lineTo(cx, yScale(stats.whiskerLow));
      ctx.stroke();

      // Whisker caps
      ctx.beginPath();
      ctx.moveTo(cx - boxWidth * 0.3, yScale(stats.whiskerHigh));
      ctx.lineTo(cx + boxWidth * 0.3, yScale(stats.whiskerHigh));
      ctx.moveTo(cx - boxWidth * 0.3, yScale(stats.whiskerLow));
      ctx.lineTo(cx + boxWidth * 0.3, yScale(stats.whiskerLow));
      ctx.stroke();

      // Box (Q1 to Q3)
      const boxTop = yScale(stats.q3);
      const boxBot = yScale(stats.q1);
      const boxH = boxBot - boxTop;

      ctx.fillStyle = MODEL_COLORS[i % MODEL_COLORS.length] + "33";
      ctx.fillRect(cx - boxWidth / 2, boxTop, boxWidth, boxH);
      ctx.strokeStyle = MODEL_COLORS[i % MODEL_COLORS.length];
      ctx.lineWidth = 1.5;
      ctx.strokeRect(cx - boxWidth / 2, boxTop, boxWidth, boxH);

      // Median line
      const medY = yScale(stats.median);
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(cx - boxWidth / 2, medY);
      ctx.lineTo(cx + boxWidth / 2, medY);
      ctx.stroke();

      // Outliers
      stats.outliers.forEach((o) => {
        const oy = yScale(o);
        ctx.fillStyle = MODEL_COLORS[i % MODEL_COLORS.length];
        ctx.beginPath();
        ctx.arc(cx, oy, 3, 0, Math.PI * 2);
        ctx.fill();
      });

      // Median value label
      ctx.fillStyle = "#fff";
      ctx.font = "500 11px system-ui";
      ctx.textAlign = "center";
      ctx.fillText(stats.median.toFixed(2), cx, boxTop - 6);

      // X-axis label
      ctx.fillStyle = "#999";
      ctx.font = "12px system-ui";
      ctx.fillText(label, cx, height - pad.bottom + 18);
    });

    // N count
    const totalN = dataGroups.reduce((sum, s) => sum + (s ? s.n : 0), 0);
    ctx.fillStyle = "#666";
    ctx.font = "10px system-ui";
    ctx.textAlign = "right";
    ctx.fillText(`n=${totalN}`, width - pad.right, pad.top - 6);

  }, [labels, dataGroups, metricConfig]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: "100%", height: "220px" }}
    />
  );
}

// --- Horizontal Boxplot (for categories) ---------------------

function HorizontalBoxplotChart({ labels, dataGroups, metricConfig }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    const ctx = canvasRef.current.getContext("2d");
    const canvas = canvasRef.current;
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.parentElement.clientWidth;
    const rowHeight = 32;
    const height = Math.max(140, labels.length * rowHeight + 56);

    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";
    ctx.scale(dpr, dpr);

    const pad = { top: 20, right: 20, bottom: 28, left: 90 };
    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;

    ctx.clearRect(0, 0, width, height);

    const [xMin, xMax] = metricConfig.range;
    const xScale = (v) => pad.left + ((v - xMin) / (xMax - xMin)) * plotW;

    // X grid
    const gridSteps = metricConfig.key === "score" ? [0, 1, 2, 3] : [0, 0.25, 0.5, 0.75, 1.0];
    ctx.textAlign = "center";
    ctx.font = "11px system-ui";

    gridSteps.forEach((v) => {
      if (v < xMin || v > xMax) return;
      const x = xScale(v);
      ctx.strokeStyle = "rgba(102,102,102,0.15)";
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo(x, pad.top);
      ctx.lineTo(x, height - pad.bottom);
      ctx.stroke();
      ctx.fillStyle = "#666";
      ctx.fillText(v % 1 === 0 ? v.toString() : v.toFixed(2), x, height - pad.bottom + 16);
    });

    // Rows
    const boxHeight = Math.min(20, rowHeight - 8);
    const gap = plotH / labels.length;

    labels.forEach((label, i) => {
      const stats = dataGroups[i];
      if (!stats) return;

      const cy = pad.top + gap * i + gap / 2;
      const color = CATEGORY_COLORS[label.toLowerCase()] || DEFAULT_CAT_COLOR;

      // Whisker line
      ctx.strokeStyle = "#888";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(xScale(stats.whiskerLow), cy);
      ctx.lineTo(xScale(stats.whiskerHigh), cy);
      ctx.stroke();

      // Whisker caps
      ctx.beginPath();
      ctx.moveTo(xScale(stats.whiskerLow), cy - boxHeight * 0.3);
      ctx.lineTo(xScale(stats.whiskerLow), cy + boxHeight * 0.3);
      ctx.moveTo(xScale(stats.whiskerHigh), cy - boxHeight * 0.3);
      ctx.lineTo(xScale(stats.whiskerHigh), cy + boxHeight * 0.3);
      ctx.stroke();

      // Box
      const boxLeft = xScale(stats.q1);
      const boxRight = xScale(stats.q3);
      const boxW = boxRight - boxLeft;

      ctx.fillStyle = color + "33";
      ctx.fillRect(boxLeft, cy - boxHeight / 2, boxW, boxHeight);
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.strokeRect(boxLeft, cy - boxHeight / 2, boxW, boxHeight);

      // Median line
      const medX = xScale(stats.median);
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(medX, cy - boxHeight / 2);
      ctx.lineTo(medX, cy + boxHeight / 2);
      ctx.stroke();

      // Outliers
      stats.outliers.forEach((o) => {
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(xScale(o), cy, 3, 0, Math.PI * 2);
        ctx.fill();
      });

      // Category label
      ctx.fillStyle = "#ccc";
      ctx.font = "12px system-ui";
      ctx.textAlign = "right";
      ctx.fillText(label, pad.left - 8, cy + 4);

      // Median value
      ctx.fillStyle = "#999";
      ctx.font = "10px system-ui";
      ctx.textAlign = "left";
      ctx.fillText(stats.median.toFixed(2), xScale(stats.whiskerHigh) + 6, cy + 4);
    });

  }, [labels, dataGroups, metricConfig]);

  const height = Math.max(140, labels.length * 32 + 56);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: "100%", height: `${height}px` }}
    />
  );
}

// --- Scatter Plot (response times) ---------------------------

function ScatterChart({ results, models }) {
  const canvasRef = useRef(null);
  const tooltipRef = useRef(null);

  const modelColorMap = useMemo(() => {
    const map = {};
    models.forEach((m, i) => {
      map[m] = MODEL_COLORS[i % MODEL_COLORS.length];
    });
    return map;
  }, [models]);

  useEffect(() => {
    if (!canvasRef.current || results.length === 0) return;

    const ctx = canvasRef.current.getContext("2d");
    const canvas = canvasRef.current;
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.parentElement.clientWidth;
    const height = 200;

    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";
    ctx.scale(dpr, dpr);

    const pad = { top: 16, right: 20, bottom: 32, left: 44 };
    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;

    ctx.clearRect(0, 0, width, height);

    const maxIndex = Math.max(...results.map((r) => r.index), 10);
    const maxTime = Math.max(...results.map((r) => r.time).filter(Boolean), 5);
    const yMax = Math.ceil(maxTime / 5) * 5;

    const xScale = (v) => pad.left + (v / maxIndex) * plotW;
    const yScale = (v) => pad.top + plotH - (v / yMax) * plotH;

    // Y grid
    const ySteps = yMax <= 10 ? 5 : yMax <= 30 ? 6 : 5;
    for (let i = 0; i <= ySteps; i++) {
      const v = (yMax / ySteps) * i;
      const y = yScale(v);
      ctx.strokeStyle = "rgba(102,102,102,0.15)";
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(width - pad.right, y);
      ctx.stroke();
      ctx.fillStyle = "#666";
      ctx.font = "11px system-ui";
      ctx.textAlign = "right";
      ctx.fillText(`${Math.round(v)}s`, pad.left - 6, y + 4);
    }

    // X labels
    ctx.fillStyle = "#666";
    ctx.font = "11px system-ui";
    ctx.textAlign = "center";
    const xSteps = Math.min(maxIndex, 8);
    for (let i = 0; i <= xSteps; i++) {
      const v = Math.round((maxIndex / xSteps) * i);
      ctx.fillText(`Q${v}`, xScale(v), height - pad.bottom + 18);
    }

    // Dots
    const dots = [];
    results.forEach((r) => {
      if (r.time == null) return;
      const x = xScale(r.index);
      const y = yScale(r.time);
      const color = modelColorMap[r.model] || DEFAULT_CAT_COLOR;

      ctx.fillStyle = color + "cc";
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.stroke();

      dots.push({ x, y, r: r });
    });

    // Store dots for hover
    canvas._dots = dots;

  }, [results, modelColorMap]);

  // Hover handler
  useEffect(() => {
    const canvas = canvasRef.current;
    const tooltip = tooltipRef.current;
    if (!canvas || !tooltip) return;

    const handleMove = (e) => {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;

      const dots = canvas._dots || [];
      const hit = dots.find((d) => Math.hypot(d.x - mx, d.y - my) < 8);

      if (hit) {
        const r = hit.r;
        tooltip.style.display = "block";
        tooltip.style.left = `${hit.x + 12}px`;
        tooltip.style.top = `${hit.y - 10}px`;
        tooltip.innerHTML = `
          <div style="font-weight:500;color:#fff;margin-bottom:2px;">Q${r.index}: ${r.question || "—"}</div>
          <div>Score: ${r.score} · BERT: ${r.bert_score?.toFixed(2) ?? "—"}</div>
          <div>${r.time?.toFixed(1)}s · ${r.model} · ${r.router_profil || ""}</div>
          <div>Kategorie: ${r.kategorie || "—"}</div>
        `;
      } else {
        tooltip.style.display = "none";
      }
    };

    const handleLeave = () => {
      tooltip.style.display = "none";
    };

    canvas.addEventListener("mousemove", handleMove);
    canvas.addEventListener("mouseleave", handleLeave);
    return () => {
      canvas.removeEventListener("mousemove", handleMove);
      canvas.removeEventListener("mouseleave", handleLeave);
    };
  }, [results]);

  return (
    <div style={{ position: "relative" }}>
      <canvas
        ref={canvasRef}
        style={{ width: "100%", height: "200px", cursor: "crosshair" }}
      />
      <div
        ref={tooltipRef}
        className="absolute pointer-events-none bg-dark_background border border-terminal_gray/30 rounded px-3 py-2 text-xs text-terminal_gray z-10"
        style={{ display: "none", maxWidth: "300px" }}
      />
    </div>
  );
}

// --- Legend ---------------------------------------------------

function Legend({ items }) {
  return (
    <div className="flex flex-wrap gap-4 text-xs text-terminal_gray">
      {items.map((item) => (
        <span key={item.label} className="flex items-center gap-1.5">
          <span
            className="w-2.5 h-2.5 rounded-sm shrink-0"
            style={{ backgroundColor: item.color }}
          />
          {item.label}
        </span>
      ))}
    </div>
  );
}

// --- Main Component ------------------------------------------

export default function LiveCharts({ results = [], gridConfig = {} }) {

  const [paramMetrics, setParamMetrics] = useState({});
  const [categoryMetric, setCategoryMetric] = useState("score");

  // --- Determine which parameters have multiple values --------

  const variableParams = useMemo(() => {
    const params = [];

    // Check gridConfig.params
    if (gridConfig.params) {
      Object.entries(gridConfig.params).forEach(([key, values]) => {
        if (values && values.length > 1) {
          params.push({ key, values, type: "param" });
        }
      });
    }

    // Check gridConfig.pipeline
    if (gridConfig.pipeline) {
      Object.entries(gridConfig.pipeline).forEach(([key, values]) => {
        if (values && values.length > 1) {
          params.push({ key, values: values.map((v) => v ? "on" : "off"), type: "pipeline" });
        }
      });
    }

    // Check models
    if (gridConfig.models && gridConfig.models.length > 1) {
      params.push({ key: "models", values: gridConfig.models, type: "model" });
    }

    return params;
  }, [gridConfig]);

  // --- Compute boxplot data per parameter per metric ----------

  const paramChartData = useMemo(() => {
    return variableParams.map((param) => {
      const metricKey = paramMetrics[param.key] || "score";
      const metric = METRICS.find((m) => m.key === metricKey);

      const labels = param.values.map((v) => {
        if (param.type === "model") return v.split(":")[0];
        if (param.type === "param") return `${param.key}=${v}`;
        return `${param.key}=${v}`;
      });

      const dataGroups = param.values.map((val) => {
        const filtered = results.filter((r) => {
          if (param.type === "model") return r.model === val;
          if (param.type === "pipeline") {
            const rVal = r.params?.[param.key] ? "on" : "off";
            return rVal === val;
          }
          return r.params?.[param.key] == val;
        });

        const scores = filtered
          .map((r) => r[metricKey])
          .filter((v) => v != null);

        return calcBoxStats(scores);
      });

      return { param, labels, dataGroups, metric };
    });
  }, [variableParams, results, paramMetrics]);

  // --- Compute category boxplot data --------------------------

  const categoryData = useMemo(() => {
    const metric = METRICS.find((m) => m.key === categoryMetric);
    const categories = [...new Set(results.map((r) => r.kategorie).filter(Boolean))];
    categories.sort();

    const dataGroups = categories.map((cat) => {
      const scores = results
        .filter((r) => r.kategorie === cat)
        .map((r) => r[categoryMetric])
        .filter((v) => v != null);
      return calcBoxStats(scores);
    });

    return { labels: categories, dataGroups, metric };
  }, [results, categoryMetric]);

  // --- Model list for scatter legend --------------------------

  const models = useMemo(() => {
    return [...new Set(results.map((r) => r.model).filter(Boolean))];
  }, [results]);

  const modelLegend = models.map((m, i) => ({
    label: m.split(":")[0],
    color: MODEL_COLORS[i % MODEL_COLORS.length],
  }));

  // --- Empty state --------------------------------------------

  if (results.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-terminal_gray/40 text-sm">
        Waiting for results…
      </div>
    );
  }

  // --- Render -------------------------------------------------

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">

      {/* Parameter boxplots — auto-grid */}
      {paramChartData.length > 0 && (
        <div className={`grid gap-4 ${
          paramChartData.length === 1 ? "grid-cols-1" :
          paramChartData.length <= 4 ? "grid-cols-2" : "grid-cols-3"
        }`}>
          {paramChartData.map(({ param, labels, dataGroups, metric }) => (
            <div
              key={param.key}
              className="bg-surface_dark rounded-lg border border-terminal_gray/10 p-3"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-white">{param.key}</span>
                <MetricTabs
                  activeMetric={paramMetrics[param.key] || "score"}
                  onChange={(m) => setParamMetrics((prev) => ({ ...prev, [param.key]: m }))}
                />
              </div>
              <VerticalBoxplotChart
                title={param.key}
                labels={labels}
                dataGroups={dataGroups}
                metricConfig={metric}
              />
            </div>
          ))}
        </div>
      )}

      {/* Category boxplot — horizontal, full width */}
      <div className="bg-surface_dark rounded-lg border border-terminal_gray/10 p-3">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium text-white">Categories</span>
          <MetricTabs
            activeMetric={categoryMetric}
            onChange={setCategoryMetric}
          />
        </div>
        <HorizontalBoxplotChart
          labels={categoryData.labels}
          dataGroups={categoryData.dataGroups}
          metricConfig={categoryData.metric}
        />
      </div>

      {/* Response time scatter — full width */}
      <div className="bg-surface_dark rounded-lg border border-terminal_gray/10 p-3">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium text-white">Response time</span>
          <Legend items={modelLegend} />
        </div>
        <ScatterChart results={results} models={models} />
      </div>
    </div>
  );
}