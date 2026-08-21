import { useMemo, useState } from "react";
import {
  ShieldCheck,
  Activity,
  CheckCircle2,
  AlertTriangle,
  Filter,
  Search,
  Info,
  Layers,
  ChevronDown,
  ChevronUp,
  Tag,
  TrendingUp,
  TrendingDown,
  Minus,
  Sparkles,
  Workflow,
  Cpu,
} from "lucide-react";
import {
  useDefectCounts,
  useRatingsData,
  type BenchmarkRun,
  type DefectCorrelationMatrix,
  type CorrelationCell,
} from "../hooks/useRatingsData";
import "./RatingsDashboard.css";

/** Dependency-free high-precision SVG line chart with interactive hover tooltip and guides */
function TrendChart({
  runs,
  seriesA,
  seriesB,
  labelA,
  labelB,
  unit = "",
  height = 180,
}: {
  runs: BenchmarkRun[];
  seriesA: (r: BenchmarkRun) => number;
  seriesB: (r: BenchmarkRun) => number;
  labelA: string;
  labelB: string;
  unit?: string;
  height?: number;
}) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const width = 640;
  const paddingX = 40;
  const paddingY = 28;

  const valuesA = runs.map(seriesA);
  const valuesB = runs.map(seriesB);
  const all = [...valuesA, ...valuesB];
  const minVal = Math.min(...all);
  const maxVal = Math.max(...all);
  const span = maxVal - minVal || 1;

  const getX = (i: number) => paddingX + (i / Math.max(1, runs.length - 1)) * (width - paddingX * 2);
  const getY = (v: number) => height - paddingY - ((v - minVal) / span) * (height - paddingY * 2);

  const pointsA = valuesA.map((v, i) => `${getX(i).toFixed(1)},${getY(v).toFixed(1)}`).join(" ");
  const pointsB = valuesB.map((v, i) => `${getX(i).toFixed(1)},${getY(v).toFixed(1)}`).join(" ");

  if (runs.length === 0) {
    return (
      <div className="trend-chart-empty">
        <Activity size={18} />
        <span>No historical automated runs recorded.</span>
      </div>
    );
  }

  const activeRun = hoverIndex !== null ? runs[hoverIndex] : null;
  const activeValA = hoverIndex !== null ? valuesA[hoverIndex] : null;
  const activeValB = hoverIndex !== null ? valuesB[hoverIndex] : null;

  return (
    <div className="trend-chart-container">
      <div className="trend-chart-header">
        <div className="trend-legends">
          <div className="legend-item asp">
            <span className="legend-dot" />
            <span className="legend-name">{labelA}</span>
            {activeValA !== null && <span className="legend-val">{activeValA.toFixed(2)}{unit}</span>}
          </div>
          <div className="legend-item simple">
            <span className="legend-dot" />
            <span className="legend-name">{labelB}</span>
            {activeValB !== null && <span className="legend-val">{activeValB.toFixed(2)}{unit}</span>}
          </div>
        </div>
        {activeRun && (
          <span className="trend-hover-stamp">
            Run #{hoverIndex! + 1} • {new Date(activeRun.timestamp).toLocaleDateString()}
          </span>
        )}
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="trend-chart-svg"
        role="img"
        aria-label={`${labelA} vs ${labelB} over time`}
        onMouseLeave={() => setHoverIndex(null)}
      >
        {/* Horizontal grid lines */}
        {[0, 0.33, 0.66, 1].map((pct, idx) => {
          const y = paddingY + pct * (height - paddingY * 2);
          const val = maxVal - pct * span;
          return (
            <g key={idx} className="chart-grid-line">
              <line x1={paddingX} y1={y} x2={width - paddingX} y2={y} />
              <text x={paddingX - 8} y={y + 3} textAnchor="end" className="chart-axis-label">
                {val.toFixed(1)}
              </text>
            </g>
          );
        })}

        {/* Polylines */}
        <polyline points={pointsB} className="trend-poly simple" />
        <polyline points={pointsA} className="trend-poly asp" />

        {/* Interactive Hover Vertical Bar & Points */}
        {runs.map((_, i) => {
          const x = getX(i);
          const yA = getY(valuesA[i]);
          const yB = getY(valuesB[i]);
          const isHovered = hoverIndex === i;

          return (
            <g
              key={i}
              className="chart-interactive-col"
              onMouseEnter={() => setHoverIndex(i)}
            >
              <rect
                x={x - (width / runs.length) / 2}
                y={paddingY}
                width={width / runs.length}
                height={height - paddingY * 2}
                className="chart-hover-hitbox"
              />
              {isHovered && (
                <>
                  <line x1={x} y1={paddingY} x2={x} y2={height - paddingY} className="chart-cursor-line" />
                  <circle cx={x} cy={yA} r={4} className="chart-point asp" />
                  <circle cx={x} cy={yB} r={4} className="chart-point simple" />
                </>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/** Coherence Score Distribution Histogram */
function ScoreHistogram({
  scores,
  title,
  subtitle,
  accent = "cyan",
}: {
  scores: number[];
  title: string;
  subtitle: string;
  accent?: "cyan" | "emerald";
}) {
  const buckets = [0, 1, 2, 3, 4].map((k) => scores.filter((s) => Math.round(s) === k).length);
  const max = Math.max(1, ...buckets);
  const total = scores.length || 1;

  const scoreLabels = [
    "0 (Broken)",
    "1 (Severe)",
    "2 (Mixed)",
    "3 (Good)",
    "4 (Flawless)",
  ];

  return (
    <div className={`histogram-card accent-${accent}`}>
      <div className="histogram-header">
        <div>
          <h4>{title}</h4>
          <span className="histogram-sub">{subtitle}</span>
        </div>
        <span className="histogram-count-pill">{scores.length} samples</span>
      </div>

      <div className="histogram-bars">
        {buckets.map((count, k) => {
          const pct = Math.round((count / total) * 100);
          return (
            <div key={k} className="bar-column">
              <span className="bar-pct">{pct}%</span>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{ height: `${(count / max) * 100}%` }}
                />
              </div>
              <span className="bar-grade">{k}</span>
              <span className="bar-label-tip">{scoreLabels[k]}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** M2.5a (#32) Per-Defect Category & Stage-Attributed Correlation Matrix Component */
function DefectCorrelationSection({ matrix }: { matrix: DefectCorrelationMatrix }) {
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [viewMode, setViewMode] = useState<"detection" | "subset">("detection");
  const [activeCell, setActiveCell] = useState<{
    defect: string;
    metricKey: string;
    cell: CorrelationCell;
  } | null>(null);

  const metrics = Object.values(matrix.metric_catalog);
  const defects = Object.values(matrix.defect_summaries);

  const filteredDefects = useMemo(() => {
    if (selectedCategory === "all") return defects;
    return defects.filter((d) => d.category === selectedCategory);
  }, [defects, selectedCategory]);

  const activeMatrix = viewMode === "detection" ? matrix.defect_detection_correlation : matrix.defect_subset_correlation;

  const getDiagnosisClass = (diagnosis: string) => {
    switch (diagnosis) {
      case "tracks_quality":
        return "cell-tracks";
      case "inverse_misleading":
        return "cell-inverse";
      case "no_signal":
        return "cell-neutral";
      default:
        return "cell-empty";
    }
  };

  const getDiagnosisBadge = (diagnosis: string) => {
    switch (diagnosis) {
      case "tracks_quality":
        return (
          <span className="matrix-badge-tag tracks">
            <TrendingUp size={12} />
            <span>Tracks Human Quality</span>
          </span>
        );
      case "inverse_misleading":
        return (
          <span className="matrix-badge-tag inverse">
            <TrendingDown size={12} />
            <span>Inverted / Misleading</span>
          </span>
        );
      case "no_signal":
        return (
          <span className="matrix-badge-tag neutral">
            <Minus size={12} />
            <span>No Clear Signal</span>
          </span>
        );
      default:
        return (
          <span className="matrix-badge-tag insufficient">
            <span>Insufficient N</span>
          </span>
        );
    }
  };

  return (
    <section className="dash-card defect-matrix-section">
      <div className="card-header-flex">
        <div>
          <div className="card-tag">Milestone §M2.5a (#32) • Empirical Metric Audit</div>
          <h3 className="card-title">Per-Defect Failure Mode &amp; Stage Correlation Matrix</h3>
        </div>
        <div className="matrix-view-toggle">
          <button
            className={`matrix-toggle-btn ${viewMode === "detection" ? "active" : ""}`}
            onClick={() => setViewMode("detection")}
            title="Measures how well the metric rewards clean outputs free of this defect"
          >
            <span>Defect Absence Discrimination</span>
          </button>
          <button
            className={`matrix-toggle-btn ${viewMode === "subset" ? "active" : ""}`}
            onClick={() => setViewMode("subset")}
            title="Measures correlation on the subset of cases exhibiting this defect"
          >
            <span>Within-Defect Subset Quality</span>
          </button>
        </div>
      </div>

      <p className="matrix-explainer">
        Correlates oriented metric deltas against human arbitration across specific failure classes.
        <strong> Positive &rho; (green)</strong> represents signals that correctly reward clean cel construction.
        <strong> Negative &rho; (red)</strong> indicates metrics that are paradoxically inflated by catastrophic artifacts (e.g. sharp torn seams or duplicated line art masquerading as high frequency detail).
      </p>

      {/* Stage Category Filters */}
      <div className="matrix-category-filters">
        <span className="filter-label">Pipeline Stage Scope:</span>
        <button
          className={`stage-filter-chip ${selectedCategory === "all" ? "active" : ""}`}
          onClick={() => setSelectedCategory("all")}
        >
          <span>All Failure Classes</span>
          <span className="chip-count">{defects.length}</span>
        </button>
        <button
          className={`stage-filter-chip ${selectedCategory === "structural" ? "active" : ""}`}
          onClick={() => setSelectedCategory("structural")}
        >
          <Workflow size={13} className="opacity-70" />
          <span>Structural &amp; Alignment (Stages 5–8)</span>
          <span className="chip-count">{defects.filter((d) => d.category === "structural").length}</span>
        </button>
        <button
          className={`stage-filter-chip ${selectedCategory === "temporal" ? "active" : ""}`}
          onClick={() => setSelectedCategory("temporal")}
        >
          <Cpu size={13} className="opacity-70" />
          <span>Temporal &amp; Masking (Stage 9)</span>
          <span className="chip-count">{defects.filter((d) => d.category === "temporal").length}</span>
        </button>
        <button
          className={`stage-filter-chip ${selectedCategory === "photometric" ? "active" : ""}`}
          onClick={() => setSelectedCategory("photometric")}
        >
          <Sparkles size={13} className="opacity-70" />
          <span>Photometric &amp; Seams (Stage 11)</span>
          <span className="chip-count">{defects.filter((d) => d.category === "photometric").length}</span>
        </button>
        <button
          className={`stage-filter-chip ${selectedCategory === "canvas" ? "active" : ""}`}
          onClick={() => setSelectedCategory("canvas")}
        >
          <Layers size={13} className="opacity-70" />
          <span>Canvas &amp; Crop (Stages 8–9)</span>
          <span className="chip-count">{defects.filter((d) => d.category === "canvas").length}</span>
        </button>
      </div>

      {/* Interactive Heatmap Matrix Grid */}
      <div className="heatmap-scroll-wrapper">
        <table className="heatmap-matrix-table">
          <thead>
            <tr>
              <th className="sticky-col header-corner">
                <span>Defect Signature</span>
                <span className="sub-header-corner">Attributed Pipeline Stage</span>
              </th>
              {metrics.map((m) => (
                <th key={m.key} className="heatmap-metric-header">
                  <div className="metric-header-title">{m.label}</div>
                  <div className="metric-header-dir">
                    {m.higher_is_better ? "Higher is better" : "Lower is better"}
                  </div>
                  {matrix.overall_corpus_correlation[m.key]?.rho !== null && (
                    <div className="metric-overall-rho font-mono">
                      Corpus &rho;: {matrix.overall_corpus_correlation[m.key].rho! > 0 ? "+" : ""}
                      {matrix.overall_corpus_correlation[m.key].rho?.toFixed(2)}
                    </div>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredDefects.map((defect) => (
              <tr key={defect.defect} className="heatmap-row">
                <td className="sticky-col defect-row-header">
                  <div className="defect-title-row">
                    <span className="defect-name">{defect.label}</span>
                    <span className="defect-count-pill font-mono">{defect.count} cases</span>
                  </div>
                  <div className="defect-stage-row">
                    <span className={`defect-cat-tag ${defect.category}`}>{defect.category.toUpperCase()}</span>
                    <span className="defect-stage-name">{defect.stage_name}</span>
                  </div>
                </td>
                {metrics.map((m) => {
                  const cell = activeMatrix[defect.defect]?.[m.key] ?? {
                    rho: null,
                    p_value: null,
                    n: 0,
                    diagnosis: "insufficient_data",
                  };
                  const isSelected =
                    activeCell?.defect === defect.defect && activeCell?.metricKey === m.key;

                  return (
                    <td
                      key={m.key}
                      className={`heatmap-cell ${getDiagnosisClass(cell.diagnosis)} ${isSelected ? "selected" : ""}`}
                      onClick={() =>
                        setActiveCell(
                          isSelected ? null : { defect: defect.defect, metricKey: m.key, cell }
                        )
                      }
                      tabIndex={0}
                      role="button"
                      aria-label={`${defect.label} vs ${m.label} correlation ${cell.rho ?? "N/A"}`}
                    >
                      <div className="cell-content font-mono">
                        {cell.rho !== null ? (
                          <>
                            <span className="cell-rho">
                              {cell.rho > 0 ? "+" : ""}
                              {cell.rho.toFixed(2)}
                            </span>
                            <span className="cell-sub-p">p={cell.p_value?.toFixed(3)}</span>
                          </>
                        ) : (
                          <span className="cell-empty-dash">&mdash;</span>
                        )}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Selected Cell Inspection Drawer */}
      {activeCell && (
        <div className="matrix-inspector-card">
          <div className="inspector-header">
            <div className="inspector-titles">
              <span className="inspector-kicker">Diagnostic Cell Deep-Dive</span>
              <h4>
                {matrix.defect_summaries[activeCell.defect]?.label} &times;{" "}
                {matrix.metric_catalog[activeCell.metricKey]?.label}
              </h4>
            </div>
            <button className="inspector-close-btn" onClick={() => setActiveCell(null)}>
              &times;
            </button>
          </div>

          <div className="inspector-grid">
            <div className="inspector-stat-col">
              <span className="stat-label">Spearman Rank Correlation (&rho;)</span>
              <div className="stat-val-flex font-mono">
                <span className="stat-huge-rho">
                  {activeCell.cell.rho !== null
                    ? `${activeCell.cell.rho > 0 ? "+" : ""}${activeCell.cell.rho.toFixed(3)}`
                    : "N/A"}
                </span>
                {getDiagnosisBadge(activeCell.cell.diagnosis)}
              </div>
              <span className="stat-sub">
                p-value: {activeCell.cell.p_value?.toFixed(4) ?? "N/A"} • N = {activeCell.cell.n} test cases
              </span>
            </div>

            <div className="inspector-meta-col">
              <div className="inspector-row">
                <span className="meta-key">Responsible Pipeline Stage:</span>
                <span className="meta-val font-mono text-cyan-300">
                  {matrix.defect_summaries[activeCell.defect]?.stage_name}
                </span>
              </div>
              <div className="inspector-row">
                <span className="meta-key">Defect Prevalence:</span>
                <span className="meta-val">
                  {matrix.defect_summaries[activeCell.defect]?.count} cases (
                  {matrix.defect_summaries[activeCell.defect]?.prevalence_pct}% of corpus)
                </span>
              </div>
              <div className="inspector-row">
                <span className="meta-key">Mean Human Scores on Defect:</span>
                <span className="meta-val font-mono">
                  ASP {matrix.defect_summaries[activeCell.defect]?.mean_asp_score} vs SCANS{" "}
                  {matrix.defect_summaries[activeCell.defect]?.mean_simple_score}
                </span>
              </div>
            </div>

            <div className="inspector-analysis-col">
              <span className="meta-key">Engineering Takeaway:</span>
              <p className="analysis-text">
                {activeCell.cell.diagnosis === "tracks_quality"
                  ? "This metric reliably penalizes the artifact and moves in harmony with human visual judgments. It can safely serve as a diagnostic evaluator."
                  : activeCell.cell.diagnosis === "inverse_misleading"
                  ? "This metric is paradoxically triggered by the visual defect — high-frequency step discontinuities and duplicated line edges falsely register as 'sharpness' or 'rich detail'. It must never be used as a standalone gating signal."
                  : "No statistically significant rank discrimination observed for this defect mode."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Stage Attribution Architecture Insights */}
      <div className="stage-attribution-grid">
        {Object.entries(matrix.stage_groups).map(([cat, grp]) => {
          const topMetric = Object.entries(grp.metrics_avg_rho)
            .filter(([, v]) => v !== null)
            .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))[0];
          const worstMetric = Object.entries(grp.metrics_avg_rho)
            .filter(([, v]) => v !== null)
            .sort((a, b) => (a[1] ?? 0) - (b[1] ?? 0))[0];

          return (
            <div key={cat} className={`stage-group-card ${cat}`}>
              <div className="stage-group-header">
                <span className={`stage-badge ${cat}`}>{cat.toUpperCase()}</span>
                <h4>{grp.stage_name}</h4>
              </div>
              <p className="stage-defects-list">
                <strong>Failure Classes:</strong> {grp.defects.map((d) => d.replace(/_/g, " ")).join(", ")}
              </p>
              <div className="stage-signals-summary">
                {topMetric && (
                  <div className="signal-item positive">
                    <span className="sig-label">Best Discriminator:</span>
                    <span className="sig-metric">{matrix.metric_catalog[topMetric[0]]?.label}</span>
                    <span className="sig-rho font-mono">+{topMetric[1]?.toFixed(2)}</span>
                  </div>
                )}
                {worstMetric && worstMetric[1] !== null && worstMetric[1] < 0 && (
                  <div className="signal-item negative">
                    <span className="sig-label">Strongest Inversion:</span>
                    <span className="sig-metric">{matrix.metric_catalog[worstMetric[0]]?.label}</span>
                    <span className="sig-rho font-mono">{worstMetric[1]?.toFixed(2)}</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default function RatingsDashboard() {
  const {
    loading,
    error,
    humanRatings,
    benchmarkResults,
    m0Data,
    defectCorrelation,
    benchmarkSubsets,
    meta,
  } = useRatingsData();
  const defectCounts = useDefectCounts(humanRatings?.evaluations);

  // Filter States
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPreference, setSelectedPreference] = useState<string>("all");
  const [selectedDefect, setSelectedDefect] = useState<string>("all");
  const [selectedTier, setSelectedTier] = useState<string>("all");
  const [selectedSubset, setSelectedSubset] = useState<string>("all");
  const [expandedTest, setExpandedTest] = useState<string | null>(null);

  const rawRows = useMemo(
    () => Object.entries(humanRatings?.evaluations ?? {}).sort(([a], [b]) => a.localeCompare(b)),
    [humanRatings],
  );

  // Provenance and relabeled metadata (M0 / C0.5)
  const enrichedRows = useMemo(() => {
    return rawRows.map(([name, entry]) => {
      // Use real safety tier if present in metadata, otherwise label audit pending
      const tier = (entry as Record<string, unknown>).safety_tier as string | undefined ?? "audit_pending";
      const tags = ((entry as Record<string, unknown>).tags as string[] | undefined) ?? [];
      const m0Case = m0Data?.cases?.[name];

      return {
        name,
        entry,
        tier,
        tags,
        m0Case,
      };
    });
  }, [rawRows, m0Data]);



  // Filtered rows
  const filteredRows = useMemo(() => {
    return enrichedRows.filter(({ name, entry, tier, tags }) => {
      // Subset Selection Filter (M2.5a)
      if (selectedSubset !== "all" && benchmarkSubsets?.subsets?.[selectedSubset]) {
        const subsetCases = new Set(benchmarkSubsets.subsets[selectedSubset].cases);
        if (!subsetCases.has(name)) return false;
      }

      // Search
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const matchesName = name.toLowerCase().includes(q);
        const matchesNotes = (entry.notes ?? "").toLowerCase().includes(q);
        const matchesDefects = (entry.defects ?? []).some((d) => d.toLowerCase().includes(q));
        const matchesTags = tags.some((t) => t.toLowerCase().includes(q));
        if (!matchesName && !matchesNotes && !matchesDefects && !matchesTags) return false;
      }

      // Preference
      if (selectedPreference !== "all") {
        if (selectedPreference === "asp" && entry.preference !== "asp") return false;
        if (selectedPreference === "simple" && entry.preference !== "simple") return false;
        if (selectedPreference === "tie" && entry.preference !== "tie") return false;
      }

      // Defect
      if (selectedDefect !== "all") {
        if (!(entry.defects ?? []).includes(selectedDefect)) return false;
      }

      // Safety Tier
      if (selectedTier !== "all") {
        if (tier !== selectedTier) return false;
      }

      return true;
    });
  }, [enrichedRows, selectedSubset, benchmarkSubsets, searchQuery, selectedPreference, selectedDefect, selectedTier]);

  if (loading) {
    return (
      <div className="ratings-dashboard loading-view">
        <div className="loading-spinner">
          <Activity className="animate-spin text-cyan-400" size={32} />
        </div>
        <p className="loading-text">Hydrating Optic Lab Telemetry &amp; Rating Artifacts…</p>
      </div>
    );
  }

  const preferenceCounts = humanRatings?.summary.preference_counts ?? { asp: 0, simple: 0, tie: 0 };
  const totalEvaluated = humanRatings?.summary.reviewed ?? 0;
  const aspShare = totalEvaluated > 0 ? Math.round(((preferenceCounts.asp ?? 0) / totalEvaluated) * 100) : 0;
  const simpleShare = totalEvaluated > 0 ? Math.round(((preferenceCounts.simple ?? 0) / totalEvaluated) * 100) : 0;
  const tieShare = totalEvaluated > 0 ? Math.round(((preferenceCounts.tie ?? 0) / totalEvaluated) * 100) : 0;

  return (
    <div className="ratings-dashboard">
      {/* Top Breadcrumb & Metadata Badge */}
      <div className="dash-kicker">
        <span className="kicker-pill">
          <Layers size={13} />
          <span>Optic Lab Analytics</span>
        </span>
        <span className="kicker-divider">/</span>
        <span className="kicker-text">Human Coherence &amp; Provenance Stream</span>
      </div>

      {/* Main Header */}
      <header className="dash-hero">
        <div className="dash-hero-title-group">
          <h1>Benchmark &amp; Human Coherence Ratings</h1>
          <p className="dash-lead">
            Granular evaluation matrix comparing neural multi-frame alignment (ASP) against classical phase-correlation stitching (SCANS).
          </p>
        </div>

        <div className="dash-callout-panel">
          <div className="callout-icon">
            <Info size={20} />
          </div>
          <div className="callout-body">
            <strong>Methodology Ground Truth Directive:</strong>
            <p>
              Automated image metrics (SSIM, Sobel sharpness, SIQE ghosting) do <em>not</em> reflect structural cel coherence. A sharp seam edge falsely inflates automated CV sharpness while creating catastrophic visual tearing. Human blind reviews serve as the authoritative arbitration baseline.
            </p>
          </div>
        </div>
      </header>

      {error && (
        <div className="dash-alert-error">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* Primary KPI Ribbon */}
      <section className="dash-kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label-row">
            <span className="kpi-label">Human Review Coverage</span>
            <CheckCircle2 size={15} className="kpi-icon text-emerald-400" />
          </div>
          <div className="kpi-value-row">
            <span className="kpi-value">{humanRatings?.summary.reviewed}</span>
            <span className="kpi-total">/ {humanRatings?.summary.total_keys} cases</span>
          </div>
          <div className="kpi-bar-track">
            <div
              className="kpi-bar-fill emerald"
              style={{ width: `${((humanRatings?.summary.reviewed ?? 0) / (humanRatings?.summary.total_keys || 1)) * 100}%` }}
            />
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label-row">
            <span className="kpi-label">ASP Mean Coherence</span>
            <span className="kpi-badge cyan">Neural Pipeline</span>
          </div>
          <div className="kpi-value-row">
            <span className="kpi-value cyan">{humanRatings?.summary.mean_asp?.toFixed(2) ?? "—"}</span>
            <span className="kpi-scale">/ 4.00</span>
          </div>
          <span className="kpi-caption">Target: &ge; 3.20 (M4 milestone)</span>
        </div>

        <div className="kpi-card">
          <div className="kpi-label-row">
            <span className="kpi-label">SCANS Mean Coherence</span>
            <span className="kpi-badge emerald">Classical Baseline</span>
          </div>
          <div className="kpi-value-row">
            <span className="kpi-value emerald">{humanRatings?.summary.mean_simple?.toFixed(2) ?? "—"}</span>
            <span className="kpi-scale">/ 4.00</span>
          </div>
          <span className="kpi-caption">High reliability on rigid static pans</span>
        </div>

        <div className="kpi-card">
          <div className="kpi-label-row">
            <span className="kpi-label">M0 Relabeled Composition</span>
            <ShieldCheck size={15} className="kpi-icon text-cyan-400" />
          </div>
          <div className="kpi-value-row">
            <span className="kpi-value">
              {m0Data ? `${m0Data.summary.true_raw_asp_composites.count} / ${m0Data.summary.safety_fallbacks_to_scans.count}` : "43 / 54"}
            </span>
            <span className="kpi-total">Split</span>
          </div>
          <span className="kpi-caption">
            {m0Data
              ? `${m0Data.summary.true_raw_asp_composites.count} true ASP vs ${m0Data.summary.safety_fallbacks_to_scans.count} fallbacks`
              : "43 true ASP composites vs 54 SCANS fallbacks"}
          </span>
        </div>
      </section>


      {/* Corpus Composition & Safety Tiering (M0 / C0.5 Preview) */}
      <section className="dash-card provenance-card">
        <div className="card-header-flex">
          <div>
            <div className="card-tag">Corpus Architecture §M0 / §C0.5</div>
            <h3 className="card-title">Corpus Provenance &amp; Relabeled Split</h3>
          </div>
          <div className="provenance-badges">
            <span className="prov-chip tier-cyan">
              {m0Data
                ? `${m0Data.summary.true_raw_asp_composites.count} True Raw ASP (Mean ${m0Data.summary.true_raw_asp_composites.mean_human_asp_score?.toFixed(2)})`
                : "43 True Raw ASP (Mean 1.33)"}
            </span>
            <span className="prov-chip tier-emerald">
              {m0Data
                ? `${m0Data.summary.safety_fallbacks_to_scans.count} Safety Fallbacks (Mean ${m0Data.summary.safety_fallbacks_to_scans.mean_human_asp_score?.toFixed(2)})`
                : "54 Safety Fallbacks (Mean 2.56)"}
            </span>
            <span className="prov-chip tier-pending">C0.5 SFW Audit in Progress</span>
          </div>
        </div>

        <p className="prov-explainer">
          Per M0 relabeling (<code>relabel.py</code>) and the signed-off SFW corpus roadmap (Issue #41), the legacy dataset contains {m0Data?.summary.true_raw_asp_composites.count ?? 43} true raw ASP composites and {m0Data?.summary.safety_fallbacks_to_scans.count ?? 54} safety fallbacks to SCANS. The C0.5 SFW benchmark enforces an evidence-backed dual-veto gate before public promotion.
        </p>

        <div className="preference-meter-section">
          <div className="meter-header">
            <span className="meter-label">Human Preference Arbitration Split</span>
            <span className="meter-stats">
              <span className="legend-dot simple" /> SCANS: {simpleShare}% &nbsp;|&nbsp;
              <span className="legend-dot tie" /> Tie: {tieShare}% &nbsp;|&nbsp;
              <span className="legend-dot asp" /> ASP: {aspShare}%
            </span>
          </div>
          <div className="meter-track">
            <div className="meter-segment simple" style={{ width: `${simpleShare}%` }} title={`SCANS Preferred: ${simpleShare}%`} />
            <div className="meter-segment tie" style={{ width: `${tieShare}%` }} title={`Equivalent/Tie: ${tieShare}%`} />
            <div className="meter-segment asp" style={{ width: `${aspShare}%` }} title={`ASP Preferred: ${aspShare}%`} />
          </div>
        </div>
      </section>

      {/* Histograms: Side by Side */}
      <section className="dash-grid-2">
        <ScoreHistogram
          title="ASP Neural Coherence Distribution"
          subtitle="Measures character cel integrity &amp; seam invisibility"
          scores={rawRows.map(([, e]) => e.asp ?? -1).filter((v) => v >= 0)}
          accent="cyan"
        />
        <ScoreHistogram
          title="SCANS Classical Coherence Distribution"
          subtitle="Measures rigid camera translation stitch quality"
          scores={rawRows.map(([, e]) => e.simple ?? -1).filter((v) => v >= 0)}
          accent="emerald"
        />
      </section>

      {/* Defect Taxonomy Breakdown */}
      {defectCounts.length > 0 && (
        <section className="dash-card">
          <div className="card-header-flex">
            <div>
              <div className="card-tag">Diagnostic Taxonomy</div>
              <h3 className="card-title">Observed Defect Signatures (Human-Tagged)</h3>
            </div>
            <span className="text-xs text-slate-400 font-mono">{defectCounts.length} distinct defect classes</span>
          </div>
          <p className="text-xs text-slate-400 mb-4">
            Click any defect chip to filter the evaluation case studies below.
          </p>

          <div className="defect-chip-list">
            <button
              className={`defect-filter-btn ${selectedDefect === "all" ? "active" : ""}`}
              onClick={() => setSelectedDefect("all")}
            >
              <span>All Defects</span>
              <span className="count">{rawRows.length}</span>
            </button>
            {defectCounts.map(([defect, count]) => {
              const isActive = selectedDefect === defect;
              return (
                <button
                  key={defect}
                  className={`defect-filter-btn ${isActive ? "active" : ""}`}
                  onClick={() => setSelectedDefect(isActive ? "all" : defect)}
                >
                  <Tag size={12} className="opacity-60" />
                  <span className="name">{defect.replace(/_/g, " ")}</span>
                  <span className="count">{count}</span>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {/* M2.5a (#32) Per-Defect & Stage-Attributed Correlation Matrix */}
      {defectCorrelation && (
        <DefectCorrelationSection matrix={defectCorrelation} />
      )}

      {/* Main Interactive Evaluations Table */}
      <section className="dash-card table-section">
        {/* M2.5a Similarity-Based Subset Selection Filter */}
        {benchmarkSubsets && (
          <div className="subset-filter-toolbar">
            <div className="subset-toolbar-header">
              <span className="subset-toolbar-label">
                <Layers size={14} className="text-cyan-400" /> Data-Driven Mini-Benchmarks:
              </span>
              <div className="subset-chips">
                <button
                  type="button"
                  onClick={() => setSelectedSubset("all")}
                  className={`subset-chip ${selectedSubset === "all" ? "active" : ""}`}
                >
                  Full Corpus ({benchmarkSubsets.total_corpus_cases})
                </button>
                {Object.entries(benchmarkSubsets.subsets).map(([key, s]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setSelectedSubset(key)}
                    className={`subset-chip ${selectedSubset === key ? "active" : ""}`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
            {selectedSubset !== "all" && benchmarkSubsets.subsets[selectedSubset] && (
              <div className="subset-active-banner">
                <span className="subset-banner-desc">
                  <strong>{benchmarkSubsets.subsets[selectedSubset].target_milestone} Target:</strong>{" "}
                  {benchmarkSubsets.subsets[selectedSubset].description}
                </span>
                <span className="subset-banner-stats">
                  Defect Coverage: <strong>{(benchmarkSubsets.subsets[selectedSubset].fidelity.defect_coverage_ratio * 100).toFixed(0)}%</strong> &bull; Score MAE: <strong>&plusmn;{benchmarkSubsets.subsets[selectedSubset].fidelity.mean_asp_score.abs_error.toFixed(2)}</strong>
                </span>
              </div>
            )}
          </div>
        )}

        <div className="table-controls-bar">
          <div className="search-input-wrapper">
            <Search size={15} className="search-icon" />
            <input
              type="text"
              placeholder="Search by test ID (e.g. asp_test04), defect, or reviewer note…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="search-input"
            />
            {searchQuery && (
              <button onClick={() => setSearchQuery("")} className="clear-btn">
                &times;
              </button>
            )}
          </div>

          <div className="filter-dropdowns">
            {/* Preference Filter */}
            <div className="filter-select-group">
              <Filter size={13} />
              <select
                value={selectedPreference}
                onChange={(e) => setSelectedPreference(e.target.value)}
                className="filter-select"
              >
                <option value="all">All Verdicts</option>
                <option value="asp">ASP Preferred</option>
                <option value="simple">SCANS Preferred</option>
                <option value="tie">Equivalent (Tie)</option>
              </select>
            </div>

            {/* Safety Tier Filter */}
            <div className="filter-select-group">
              <ShieldCheck size={13} />
              <select
                value={selectedTier}
                onChange={(e) => setSelectedTier(e.target.value)}
                className="filter-select"
              >
                <option value="all">All Safety Statuses</option>
                <option value="audit_pending">Audit Pending (C0.5)</option>
                <option value="tier_g">Tier G (General)</option>
                <option value="tier_pg13">Tier PG-13</option>
                <option value="tier_mature_sfw">Mature SFW</option>
              </select>
            </div>
          </div>
        </div>

        <div className="table-status-bar">
          <span>Showing <strong>{filteredRows.length}</strong> of {enrichedRows.length} evaluation cases</span>
          {(selectedPreference !== "all" || selectedDefect !== "all" || selectedTier !== "all" || searchQuery) && (
            <button
              onClick={() => {
                setSelectedPreference("all");
                setSelectedDefect("all");
                setSelectedTier("all");
                setSearchQuery("");
              }}
              className="reset-filters-btn"
            >
              Reset Filters
            </button>
          )}
        </div>

        <div className="table-responsive-wrapper">
          <table className="optic-table">
            <thead>
              <tr>
                <th>Test Case</th>
                <th>Safety Status</th>
                <th>ASP (0–4)</th>
                <th>SCANS (0–4)</th>
                <th>Human Preference</th>
                <th>Tagged Defects</th>
                <th>Observation &amp; Notes</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="empty-table-cell">
                    No cases match the selected filter criteria.
                  </td>
                </tr>
              ) : (
                filteredRows.map(({ name, entry, tier, tags, m0Case }) => {
                  const isExpanded = expandedTest === name;
                  const pref = entry.preference || "tie";

                  return (
                    <>
                      <tr
                        key={name}
                        className={`table-row-item ${isExpanded ? "expanded" : ""}`}
                        onClick={() => setExpandedTest(isExpanded ? null : name)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            setExpandedTest(isExpanded ? null : name);
                          }
                        }}
                        tabIndex={0}
                        role="button"
                        aria-expanded={isExpanded}
                      >
                        <td className="font-mono font-medium text-cyan-300">
                          {name}
                        </td>
                        <td>
                          <span className={`table-tier-badge ${tier}`}>
                            {tier === "audit_pending" ? "AUDIT PENDING" : tier.replace("tier_", "").toUpperCase()}
                          </span>
                        </td>
                        <td>
                          <div className="score-cell-flex">
                            <span className="score-num font-mono">{entry.asp ?? "—"}</span>
                            {entry.asp !== undefined && (
                              <div className="mini-score-bar">
                                <div
                                  className="mini-fill cyan"
                                  style={{ width: `${(entry.asp / 4) * 100}%` }}
                                />
                              </div>
                            )}
                          </div>
                        </td>
                        <td>
                          <div className="score-cell-flex">
                            <span className="score-num font-mono">{entry.simple ?? "—"}</span>
                            {entry.simple !== undefined && (
                              <div className="mini-score-bar">
                                <div
                                  className="mini-fill emerald"
                                  style={{ width: `${(entry.simple / 4) * 100}%` }}
                                />
                              </div>
                            )}
                          </div>
                        </td>
                        <td>
                          <span className={`preference-badge ${pref}`}>
                            {pref === "asp" ? "ASP PREFERRED" : pref === "simple" ? "SCANS PREFERRED" : "EQUIVALENT"}
                          </span>
                        </td>
                        <td>
                          <div className="table-defect-chips">
                            {(entry.defects ?? []).length > 0 ? (
                              entry.defects!.map((d) => (
                                <span key={d} className="mini-defect-tag">
                                  {d.replace(/_/g, " ")}
                                </span>
                              ))
                            ) : (
                              <span className="text-slate-500 text-xs">—</span>
                            )}
                          </div>
                        </td>
                        <td className="table-notes-cell">
                          <p className="truncate-notes">{entry.notes || "—"}</p>
                        </td>
                        <td className="text-right">
                          <button className="row-toggle-btn" aria-label="Toggle details">
                            {isExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                          </button>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="table-detail-drawer-row">
                          <td colSpan={8} className="table-detail-drawer-cell">
                            <div className="detail-drawer-content">
                              <div className="drawer-grid">
                                <div>
                                  <h5 className="drawer-heading">Reviewer Assessment &amp; Rationale</h5>
                                  <p className="drawer-notes">{entry.notes || "No additional evaluator notes provided."}</p>

                                  <h5 className="drawer-heading mt-4">Pipeline &amp; Fallback Provenance (M0)</h5>
                                  <div className="drawer-provenance-info">
                                    {m0Case ? (
                                      <div className="space-y-1 text-xs font-mono">
                                        <div>
                                          <span className="text-slate-400">Rated Identity: </span>
                                          <span className={m0Case.true_raw_asp_composite ? "text-cyan-400" : "text-emerald-400"}>
                                            {m0Case.rated_identity.toUpperCase()}
                                          </span>
                                        </div>
                                        <div>
                                          <span className="text-slate-400">Gate: </span>
                                          <span className="text-slate-200">{m0Case.fallback_gate} (code {m0Case.fallback_code})</span>
                                        </div>
                                        <div>
                                          <span className="text-slate-400">Composite: </span>
                                          <span className="text-slate-300">
                                            {m0Case.true_raw_asp_composite
                                              ? "True Raw ASP Composite"
                                              : "Safety fallback to SCANS"}
                                          </span>
                                        </div>
                                      </div>
                                    ) : (
                                      <span className="text-xs text-slate-400">Provenance metadata pending</span>
                                    )}
                                  </div>
                                </div>
                                <div>
                                  <h5 className="drawer-heading">Identified Defect Signatures</h5>
                                  <div className="drawer-defect-list">
                                    {(entry.defects ?? []).length > 0 ? (
                                      entry.defects!.map((d) => (
                                        <span key={d} className="drawer-defect-badge">
                                          {d.replace(/_/g, " ")}
                                        </span>
                                      ))
                                    ) : (
                                      <span className="text-xs text-slate-400">No major defects recorded</span>
                                    )}
                                  </div>
                                  {tags.length > 0 && (
                                    <div className="drawer-tag-row">
                                      <span className="text-xs text-slate-500 font-mono">Tags:</span>
                                      {tags.map((t) => (
                                        <span key={t} className="drawer-tag">{t}</span>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>



      {/* Automated Metrics Over Time (Telemetry Stream) */}
      {benchmarkResults && benchmarkResults.runs.length > 0 && (
        <section className="dash-card">
          <div className="card-header-flex">
            <div>
              <div className="card-tag">Telemetry Stream</div>
              <h3 className="card-title">Automated Benchmarks Over Time</h3>
            </div>
            <span className="text-xs text-slate-400 font-mono">{benchmarkResults.run_count} Automated Runs</span>
          </div>
          <p className="text-xs text-slate-400 mb-6">
            Tracked across full test suite runs. Lower SIQE ghosting is better; higher Sobel sharpness represents high-frequency detail.
          </p>

          <div className="dash-grid-2">
            <div>
              <h4 className="chart-subhead">Average Sobel Sharpness Index</h4>
              <TrendChart
                runs={benchmarkResults.runs}
                seriesA={(r) => r.summary.avg_sharpness_asp}
                seriesB={(r) => r.summary.avg_sharpness_simple}
                labelA="ASP Neural"
                labelB="SCANS Classical"
              />
            </div>
            <div>
              <h4 className="chart-subhead">Average Ghosting Artifact Index (SIQE)</h4>
              <TrendChart
                runs={benchmarkResults.runs}
                seriesA={(r) => r.summary.avg_ghosting_asp}
                seriesB={(r) => r.summary.avg_ghosting_simple}
                labelA="ASP Neural"
                labelB="SCANS Classical"
              />
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
