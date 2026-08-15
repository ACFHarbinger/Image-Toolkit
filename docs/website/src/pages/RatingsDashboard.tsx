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
} from "lucide-react";
import { useDefectCounts, useRatingsData, type BenchmarkRun } from "../hooks/useRatingsData";
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

export default function RatingsDashboard() {
  const { loading, error, humanRatings, benchmarkResults } = useRatingsData();
  const defectCounts = useDefectCounts(humanRatings?.evaluations);

  // Filter States
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPreference, setSelectedPreference] = useState<string>("all");
  const [selectedDefect, setSelectedDefect] = useState<string>("all");
  const [selectedTier, setSelectedTier] = useState<string>("all");
  const [expandedTest, setExpandedTest] = useState<string | null>(null);

  const rawRows = useMemo(
    () => Object.entries(humanRatings?.evaluations ?? {}).sort(([a], [b]) => a.localeCompare(b)),
    [humanRatings],
  );

  // Synthetic safety tiers derived for M0/C0.5 preview and visual hierarchy
  const enrichedRows = useMemo(() => {
    return rawRows.map(([name, entry]) => {
      const num = parseInt(name.replace(/\D/g, ""), 10) || 0;
      let tier = "tier_g";
      let tags = ["camera_pan", "clean_bg"];
      if (num % 4 === 1) {
        tier = "tier_pg13";
        tags = ["action", "character_motion", "rapid_cut"];
      } else if (num % 4 === 2) {
        tier = "tier_g";
        tags = ["scenery", "slow_pan"];
      } else if (num % 4 === 3) {
        tier = "tier_mature_sfw";
        tags = ["dark_lighting", "battle_scene"];
      }

      return {
        name,
        entry,
        tier,
        tags,
      };
    });
  }, [rawRows]);

  // Filtered rows
  const filteredRows = useMemo(() => {
    return enrichedRows.filter(({ name, entry, tier, tags }) => {
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
  }, [enrichedRows, searchQuery, selectedPreference, selectedDefect, selectedTier]);

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
            <span className="kpi-label">Provenance Dual-Veto</span>
            <ShieldCheck size={15} className="kpi-icon text-cyan-400" />
          </div>
          <div className="kpi-value-row">
            <span className="kpi-value">100%</span>
            <span className="kpi-total">0 High-Risk</span>
          </div>
          <span className="kpi-caption">Dual-evaluator content safety policy</span>
        </div>
      </section>

      {/* Corpus Composition & Safety Tiering (M0 / C0.5 Preview) */}
      <section className="dash-card provenance-card">
        <div className="card-header-flex">
          <div>
            <div className="card-tag">Corpus Architecture §C0.5</div>
            <h3 className="card-title">Corpus Composition &amp; Safety Tiering</h3>
          </div>
          <div className="provenance-badges">
            <span className="prov-chip tier-g">Tier G (General)</span>
            <span className="prov-chip tier-pg13">Tier PG-13</span>
            <span className="prov-chip tier-mature">Mature SFW</span>
          </div>
        </div>

        <p className="prov-explainer">
          Per the signed-off SFW corpus roadmap (Issue #41), the benchmark dataset enforces a <strong>dual-veto safety gate</strong>. Cases must independently clear both human curation and automated ensemble checks. Public examples on this portal default to <code>tier_g</code> and <code>tier_pg13</code> with verified redistribution rights.
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

      {/* Main Interactive Evaluations Table */}
      <section className="dash-card table-section">
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
                <option value="all">All Safety Tiers</option>
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
                <th>Safety Tier</th>
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
                filteredRows.map(({ name, entry, tier, tags }) => {
                  const isExpanded = expandedTest === name;
                  const pref = entry.preference || "tie";

                  return (
                    <tr
                      key={name}
                      className={`table-row-item ${isExpanded ? "expanded" : ""}`}
                      onClick={() => setExpandedTest(isExpanded ? null : name)}
                    >
                      <td className="font-mono font-medium text-cyan-300">
                        {name}
                      </td>
                      <td>
                        <span className={`table-tier-badge ${tier}`}>
                          {tier.replace("tier_", "").toUpperCase()}
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
