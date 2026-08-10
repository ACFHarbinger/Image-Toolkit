import { useMemo } from "react";
import { useDefectCounts, useRatingsData, type BenchmarkRun } from "../hooks/useRatingsData";
import "./RatingsDashboard.css";

/** Dependency-free SVG line chart — one polyline per series, shared axes. */
function TrendChart({
  runs,
  seriesA,
  seriesB,
  labelA,
  labelB,
  height = 160,
}: {
  runs: BenchmarkRun[];
  seriesA: (r: BenchmarkRun) => number;
  seriesB: (r: BenchmarkRun) => number;
  labelA: string;
  labelB: string;
  height?: number;
}) {
  const width = 560;
  const padding = 28;
  const valuesA = runs.map(seriesA);
  const valuesB = runs.map(seriesB);
  const all = [...valuesA, ...valuesB];
  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = max - min || 1;

  const toPoints = (values: number[]) =>
    values
      .map((v, i) => {
        const x = padding + (i / Math.max(1, values.length - 1)) * (width - padding * 2);
        const y = height - padding - ((v - min) / span) * (height - padding * 2);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");

  if (runs.length === 0) {
    return <p className="dash-empty">No automated runs yet.</p>;
  }

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="trend-chart" role="img" aria-label={`${labelA} vs ${labelB} over time`}>
      <polyline points={toPoints(valuesA)} className="trend-line asp" />
      <polyline points={toPoints(valuesB)} className="trend-line simple" />
      <text x={padding} y={14} className="trend-legend asp">{labelA}</text>
      <text x={padding} y={30} className="trend-legend simple">{labelB}</text>
    </svg>
  );
}

function ScoreHistogram({ scores, title }: { scores: number[]; title: string }) {
  const buckets = [0, 1, 2, 3, 4].map((k) => scores.filter((s) => Math.round(s) === k).length);
  const max = Math.max(1, ...buckets);
  return (
    <div className="histogram">
      <h4>{title}</h4>
      <div className="bars">
        {buckets.map((count, k) => (
          <div key={k} className="bar-col">
            <div className="bar-track">
              <div className="bar-fill" style={{ height: `${(count / max) * 100}%` }} />
            </div>
            <span className="bar-label">{k}</span>
            <span className="bar-count">{count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function RatingsDashboard() {
  const { loading, error, humanRatings, benchmarkResults, meta } = useRatingsData();
  const defectCounts = useDefectCounts(humanRatings?.evaluations);

  const evaluationRows = useMemo(
    () => Object.entries(humanRatings?.evaluations ?? {}).sort(([a], [b]) => a.localeCompare(b)),
    [humanRatings],
  );

  if (loading) return <div className="ratings-dashboard"><p>Loading dashboard data…</p></div>;

  return (
    <div className="ratings-dashboard">
      <header>
        <h1>Benchmark &amp; Human Coherence Ratings</h1>
        <p className="dash-disclaimer">
          Human coherence judgments and automated metrics are measured
          independently and shown separately below. A high automated score
          (SSIM, sharpness, ghosting) does <strong>not</strong> imply the
          composite is structurally coherent — see{" "}
          <code>docs/moon/research/ASP_Critical_Evaluation_2026-07-08.md</code>{" "}
          for why no automated metric currently substitutes for a human
          judgment.
        </p>
      </header>

      {error && <p className="dash-error">{error}</p>}

      {meta && (
        <section className="dash-banner">
          <p>{meta.human_summary.narrative_hint}</p>
          {meta.notes.map((note, i) => (
            <p key={i} className="dash-note">{note}</p>
          ))}
        </section>
      )}

      {humanRatings && (
        <section className="dash-section">
          <h2>Human Coherence Ratings</h2>
          <div className="dash-stat-row">
            <div className="dash-stat">
              <span className="stat-value">
                {humanRatings.summary.reviewed} / {humanRatings.summary.total_keys}
              </span>
              <span className="stat-label">rating coverage</span>
            </div>
            <div className="dash-stat">
              <span className="stat-value">{humanRatings.summary.mean_asp ?? "—"}</span>
              <span className="stat-label">mean ASP coherence (0–4)</span>
            </div>
            <div className="dash-stat">
              <span className="stat-value">{humanRatings.summary.mean_simple ?? "—"}</span>
              <span className="stat-label">mean SCANS coherence (0–4)</span>
            </div>
          </div>

          <div className="dash-grid-2">
            <ScoreHistogram
              title="ASP coherence distribution"
              scores={evaluationRows.map(([, e]) => e.asp ?? -1).filter((v) => v >= 0)}
            />
            <ScoreHistogram
              title="SCANS coherence distribution"
              scores={evaluationRows.map(([, e]) => e.simple ?? -1).filter((v) => v >= 0)}
            />
          </div>

          {defectCounts.length > 0 && (
            <div className="defect-breakdown">
              <h4>Defect categories observed (human-tagged)</h4>
              <ul>
                {defectCounts.map(([defect, count]) => (
                  <li key={defect}>
                    <span className="defect-name">{defect.replace(/_/g, " ")}</span>
                    <span className="defect-count">{count}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Test</th>
                  <th>ASP</th>
                  <th>SCANS</th>
                  <th>Preference</th>
                  <th>Defects</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {evaluationRows.map(([name, e]) => (
                  <tr key={name}>
                    <td>{name}</td>
                    <td>{e.asp ?? "—"}</td>
                    <td>{e.simple ?? "—"}</td>
                    <td>{e.preference ?? "—"}</td>
                    <td>{(e.defects ?? []).join(", ") || "—"}</td>
                    <td className="notes-cell">{e.notes || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {benchmarkResults && benchmarkResults.runs.length > 0 && (
        <section className="dash-section">
          <h2>Automated Metrics Over Time</h2>
          <p className="dash-disclaimer-inline">
            Measured, not human-judged — {benchmarkResults.run_count} runs.
          </p>
          <TrendChart
            runs={benchmarkResults.runs}
            seriesA={(r) => r.summary.avg_sharpness_asp}
            seriesB={(r) => r.summary.avg_sharpness_simple}
            labelA="ASP sharpness"
            labelB="SCANS sharpness"
          />
          <TrendChart
            runs={benchmarkResults.runs}
            seriesA={(r) => r.summary.avg_ghosting_asp}
            seriesB={(r) => r.summary.avg_ghosting_simple}
            labelA="ASP ghosting"
            labelB="SCANS ghosting"
          />
        </section>
      )}
    </div>
  );
}
