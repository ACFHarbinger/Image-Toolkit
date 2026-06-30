/** Lightweight SVG chart primitives for the benchmark dashboard.
 *
 *  No third-party chart library — all rendering is pure React + SVG so the
 *  bundle stays small and the components match the Tailwind dark-mode palette
 *  used everywhere else in the app.
 */

import React from 'react';

// ── Shared helpers ────────────────────────────────────────────────────────────

const PAD = { top: 20, right: 20, bottom: 60, left: 70 };
const AXIS_COLOR = '#9ca3af'; // gray-400
const GRID_COLOR = '#374151'; // gray-700
const TEXT_COLOR = '#d1d5db'; // gray-300

function niceMax(v: number): number {
  if (v <= 0) return 1;
  const exp = Math.pow(10, Math.floor(Math.log10(v)));
  const norm = v / exp;
  const nice = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10;
  return nice * exp;
}

function formatNum(v: number): string {
  if (v >= 1000) return `${(v / 1000).toFixed(1)}k`;
  if (v >= 1 || v === 0) return v.toFixed(v % 1 === 0 ? 0 : 2);
  return v.toFixed(4);
}

interface AxisProps {
  w: number;
  h: number;
  xLabel?: string;
  yLabel?: string;
  xTicks: string[];
  yTicks: number[];
  yMax: number;
}

function Axes({ w, h, xLabel, yLabel, xTicks, yTicks, yMax }: AxisProps) {
  const iw = w - PAD.left - PAD.right;
  const ih = h - PAD.top - PAD.bottom;
  return (
    <g>
      {/* grid lines */}
      {yTicks.map(t => {
        const y = PAD.top + ih - (t / yMax) * ih;
        return (
          <line key={t} x1={PAD.left} x2={PAD.left + iw} y1={y} y2={y}
            stroke={GRID_COLOR} strokeWidth={1} strokeDasharray="4 3" />
        );
      })}
      {/* axes */}
      <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={PAD.top + ih} stroke={AXIS_COLOR} />
      <line x1={PAD.left} x2={PAD.left + iw} y1={PAD.top + ih} y2={PAD.top + ih} stroke={AXIS_COLOR} />
      {/* y ticks */}
      {yTicks.map(t => {
        const y = PAD.top + ih - (t / yMax) * ih;
        return (
          <g key={t}>
            <line x1={PAD.left - 4} x2={PAD.left} y1={y} y2={y} stroke={AXIS_COLOR} />
            <text x={PAD.left - 8} y={y + 4} textAnchor="end" fontSize={10} fill={TEXT_COLOR}>
              {formatNum(t)}
            </text>
          </g>
        );
      })}
      {/* x tick labels */}
      {xTicks.map((label, i) => {
        const x = PAD.left + (i + 0.5) * (iw / xTicks.length);
        return (
          <text key={i} x={x} y={PAD.top + ih + 16} textAnchor="end"
            fontSize={10} fill={TEXT_COLOR}
            transform={`rotate(-35, ${x}, ${PAD.top + ih + 16})`}>
            {label.length > 18 ? label.slice(0, 17) + '…' : label}
          </text>
        );
      })}
      {/* axis labels */}
      {yLabel && (
        <text x={14} y={PAD.top + ih / 2} textAnchor="middle" fontSize={11} fill={TEXT_COLOR}
          transform={`rotate(-90, 14, ${PAD.top + ih / 2})`}>{yLabel}</text>
      )}
      {xLabel && (
        <text x={PAD.left + iw / 2} y={h - 4} textAnchor="middle" fontSize={11} fill={TEXT_COLOR}>
          {xLabel}
        </text>
      )}
    </g>
  );
}

// ── Bar Chart ─────────────────────────────────────────────────────────────────

export interface BarSeries {
  label: string;
  color: string;
  values: number[];
  errorPlus?: number[];
  errorMinus?: number[];
}

interface BarChartProps {
  labels: string[];
  series: BarSeries[];
  height?: number;
  yLabel?: string;
  xLabel?: string;
  title?: string;
  stacked?: boolean;
}

export function BarChart({ labels, series, height = 320, yLabel, xLabel, title, stacked = false }: BarChartProps) {
  const w = 600;
  const h = height;
  const iw = w - PAD.left - PAD.right;
  const ih = h - PAD.top - PAD.bottom;

  const allValues = stacked
    ? labels.map((_, i) => series.reduce((s, ser) => s + (ser.values[i] ?? 0), 0))
    : series.flatMap(s => s.values);
  const rawMax = Math.max(...allValues, 0);
  const yMax = niceMax(rawMax);
  const yTicks = Array.from({ length: 5 }, (_, i) => (i / 4) * yMax);

  const barW = (iw / labels.length) * (stacked ? 0.6 : 0.6 / series.length);
  const groupW = iw / labels.length;

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} className="overflow-visible">
      {title && <text x={w / 2} y={12} textAnchor="middle" fontSize={12} fontWeight={600} fill={TEXT_COLOR}>{title}</text>}
      <Axes w={w} h={h} xLabel={xLabel} yLabel={yLabel} xTicks={labels} yTicks={yTicks} yMax={yMax} />
      <g>
        {labels.map((_, gi) => {
          const gx = PAD.left + gi * groupW;
          if (stacked) {
            let stackTop = PAD.top + ih;
            return (
              <g key={gi}>
                {series.map((ser, si) => {
                  const val = ser.values[gi] ?? 0;
                  const bh = (val / yMax) * ih;
                  const y = stackTop - bh;
                  stackTop -= bh;
                  const bx = gx + groupW * 0.2;
                  return (
                    <rect key={si} x={bx} y={y} width={barW} height={bh}
                      fill={ser.color} opacity={0.85} rx={2}>
                      <title>{`${ser.label}: ${formatNum(val)}`}</title>
                    </rect>
                  );
                })}
              </g>
            );
          }
          return (
            <g key={gi}>
              {series.map((ser, si) => {
                const val = ser.values[gi] ?? 0;
                const bh = (val / yMax) * ih;
                const y = PAD.top + ih - bh;
                const bx = gx + groupW * 0.1 + si * barW;
                const errPlus = (ser.errorPlus?.[gi] ?? 0) / yMax * ih;
                const errMinus = (ser.errorMinus?.[gi] ?? 0) / yMax * ih;
                return (
                  <g key={si}>
                    <rect x={bx} y={y} width={barW} height={bh}
                      fill={ser.color} opacity={0.85} rx={2}>
                      <title>{`${ser.label}: ${formatNum(val)}`}</title>
                    </rect>
                    {(errPlus > 0 || errMinus > 0) && (
                      <g>
                        <line x1={bx + barW / 2} x2={bx + barW / 2}
                          y1={y - errPlus} y2={y + errMinus}
                          stroke={TEXT_COLOR} strokeWidth={1.5} />
                        <line x1={bx + barW / 2 - 3} x2={bx + barW / 2 + 3}
                          y1={y - errPlus} y2={y - errPlus}
                          stroke={TEXT_COLOR} strokeWidth={1.5} />
                        <line x1={bx + barW / 2 - 3} x2={bx + barW / 2 + 3}
                          y1={y + errMinus} y2={y + errMinus}
                          stroke={TEXT_COLOR} strokeWidth={1.5} />
                      </g>
                    )}
                  </g>
                );
              })}
            </g>
          );
        })}
      </g>
    </svg>
  );
}

// ── Horizontal Bar Chart (efficiency ranking) ─────────────────────────────────

interface HBarEntry { name: string; value: number; color: string; }
interface HBarChartProps { data: HBarEntry[]; xLabel?: string; title?: string; }

export function HBarChart({ data, xLabel, title }: HBarChartProps) {
  const rowH = 30;
  const pad = { top: 24, right: 60, bottom: 30, left: 180 };
  const w = 600;
  const h = pad.top + pad.bottom + data.length * rowH;
  const iw = w - pad.left - pad.right;
  const rawMax = Math.max(...data.map(d => d.value), 0);
  const xMax = niceMax(rawMax);
  const xTicks = Array.from({ length: 5 }, (_, i) => (i / 4) * xMax);

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} className="overflow-visible">
      {title && <text x={w / 2} y={14} textAnchor="middle" fontSize={12} fontWeight={600} fill={TEXT_COLOR}>{title}</text>}
      {/* x grid + ticks */}
      {xTicks.map(t => {
        const x = pad.left + (t / xMax) * iw;
        return (
          <g key={t}>
            <line x1={x} x2={x} y1={pad.top} y2={pad.top + data.length * rowH} stroke={GRID_COLOR} strokeDasharray="4 3" />
            <text x={x} y={pad.top + data.length * rowH + 14} textAnchor="middle" fontSize={9} fill={TEXT_COLOR}>{formatNum(t)}</text>
          </g>
        );
      })}
      {/* axes */}
      <line x1={pad.left} x2={pad.left} y1={pad.top} y2={pad.top + data.length * rowH} stroke={AXIS_COLOR} />
      <line x1={pad.left} x2={pad.left + iw} y1={pad.top + data.length * rowH} y2={pad.top + data.length * rowH} stroke={AXIS_COLOR} />
      {/* bars */}
      {data.map((d, i) => {
        const barW = (d.value / xMax) * iw;
        const y = pad.top + i * rowH + rowH * 0.15;
        const bh = rowH * 0.70;
        return (
          <g key={i}>
            <text x={pad.left - 6} y={y + bh / 2 + 4} textAnchor="end" fontSize={10} fill={TEXT_COLOR}>
              {d.name.length > 22 ? d.name.slice(0, 21) + '…' : d.name}
            </text>
            <rect x={pad.left} y={y} width={barW} height={bh} fill={d.color} opacity={0.85} rx={2}>
              <title>{`${d.name}: ${formatNum(d.value)}`}</title>
            </rect>
            <text x={pad.left + barW + 4} y={y + bh / 2 + 4} fontSize={10} fill={TEXT_COLOR}>{formatNum(d.value)}</text>
          </g>
        );
      })}
      {xLabel && <text x={pad.left + iw / 2} y={h - 2} textAnchor="middle" fontSize={11} fill={TEXT_COLOR}>{xLabel}</text>}
    </svg>
  );
}

// ── Scatter Plot ──────────────────────────────────────────────────────────────

export interface ScatterDatum {
  x: number;
  y: number;
  r: number;
  color: string;
  label: string;
  tooltip?: string;
}

interface ScatterPlotProps {
  data: ScatterDatum[];
  xLabel?: string;
  yLabel?: string;
  title?: string;
  height?: number;
  logX?: boolean;
}

export function ScatterPlot({ data, xLabel, yLabel, title, height = 400, logX = false }: ScatterPlotProps) {
  const w = 600;
  const h = height;
  const iw = w - PAD.left - PAD.right;
  const ih = h - PAD.top - PAD.bottom;

  const xs = data.map(d => d.x);
  const ys = data.map(d => d.y);
  const xMin = logX ? Math.min(...xs.filter(x => x > 0)) * 0.5 : 0;
  const xMax = Math.max(...xs, 0) * 1.1 || 1;
  const yMax = niceMax(Math.max(...ys, 0));
  const yTicks = Array.from({ length: 5 }, (_, i) => (i / 4) * yMax);

  const toX = (v: number) => {
    if (logX) {
      const lMin = Math.log(xMin || 0.0001);
      const lMax = Math.log(xMax);
      return PAD.left + ((Math.log(v) - lMin) / (lMax - lMin)) * iw;
    }
    return PAD.left + (v / xMax) * iw;
  };
  const toY = (v: number) => PAD.top + ih - (v / yMax) * ih;

  const xTickVals = logX
    ? [xMin, xMin * 2, xMax * 0.25, xMax * 0.5, xMax].filter(v => v > 0)
    : Array.from({ length: 5 }, (_, i) => (i / 4) * xMax);

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} className="overflow-visible">
      {title && <text x={w / 2} y={12} textAnchor="middle" fontSize={12} fontWeight={600} fill={TEXT_COLOR}>{title}</text>}
      {/* grid */}
      {yTicks.map(t => (
        <line key={t} x1={PAD.left} x2={PAD.left + iw}
          y1={toY(t)} y2={toY(t)} stroke={GRID_COLOR} strokeDasharray="4 3" />
      ))}
      {xTickVals.map((t, i) => (
        <line key={i} x1={toX(t)} x2={toX(t)}
          y1={PAD.top} y2={PAD.top + ih} stroke={GRID_COLOR} strokeDasharray="4 3" />
      ))}
      {/* axes */}
      <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={PAD.top + ih} stroke={AXIS_COLOR} />
      <line x1={PAD.left} x2={PAD.left + iw} y1={PAD.top + ih} y2={PAD.top + ih} stroke={AXIS_COLOR} />
      {/* y ticks */}
      {yTicks.map(t => (
        <g key={t}>
          <text x={PAD.left - 6} y={toY(t) + 4} textAnchor="end" fontSize={10} fill={TEXT_COLOR}>{formatNum(t)}</text>
        </g>
      ))}
      {/* x ticks */}
      {xTickVals.map((t, i) => (
        <text key={i} x={toX(t)} y={PAD.top + ih + 14} textAnchor="middle" fontSize={10} fill={TEXT_COLOR}>{formatNum(t)}</text>
      ))}
      {/* axis labels */}
      {yLabel && <text x={14} y={PAD.top + ih / 2} textAnchor="middle" fontSize={11} fill={TEXT_COLOR} transform={`rotate(-90, 14, ${PAD.top + ih / 2})`}>{yLabel}</text>}
      {xLabel && <text x={PAD.left + iw / 2} y={h - 4} textAnchor="middle" fontSize={11} fill={TEXT_COLOR}>{xLabel}</text>}
      {/* data points */}
      {data.map((d, i) => (
        <g key={i}>
          <circle cx={toX(d.x)} cy={toY(d.y)} r={d.r} fill={d.color} opacity={0.8} stroke="rgba(0,0,0,0.3)" strokeWidth={1}>
            <title>{d.tooltip || `${d.label}\nTime: ${formatNum(d.x)}s\nMem: ${formatNum(d.y)} MB`}</title>
          </circle>
          <text x={toX(d.x)} y={toY(d.y) - d.r - 3} textAnchor="middle" fontSize={9} fill={TEXT_COLOR}>
            {d.label.length > 12 ? d.label.slice(0, 11) + '…' : d.label}
          </text>
        </g>
      ))}
    </svg>
  );
}

// ── Line / Trend Chart ────────────────────────────────────────────────────────

export interface LineSeries { label: string; color: string; points: Array<{ x: string; y: number }> }

interface LineChartProps {
  series: LineSeries[];
  yLabel?: string;
  xLabel?: string;
  title?: string;
  height?: number;
}

export function LineChart({ series, yLabel, xLabel, title, height = 280 }: LineChartProps) {
  const w = 600;
  const h = height;
  const iw = w - PAD.left - PAD.right;
  const ih = h - PAD.top - PAD.bottom;

  const allY = series.flatMap(s => s.points.map(p => p.y));
  const yMax = niceMax(Math.max(...allY, 0));
  const yTicks = Array.from({ length: 5 }, (_, i) => (i / 4) * yMax);
  const allX = [...new Set(series.flatMap(s => s.points.map(p => p.x)))].sort();
  const xStep = iw / Math.max(allX.length - 1, 1);

  const toX = (xStr: string) => PAD.left + allX.indexOf(xStr) * xStep;
  const toY = (v: number) => PAD.top + ih - (v / yMax) * ih;

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} className="overflow-visible">
      {title && <text x={w / 2} y={12} textAnchor="middle" fontSize={12} fontWeight={600} fill={TEXT_COLOR}>{title}</text>}
      {/* grid */}
      {yTicks.map(t => (
        <line key={t} x1={PAD.left} x2={PAD.left + iw} y1={toY(t)} y2={toY(t)} stroke={GRID_COLOR} strokeDasharray="4 3" />
      ))}
      {/* axes */}
      <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={PAD.top + ih} stroke={AXIS_COLOR} />
      <line x1={PAD.left} x2={PAD.left + iw} y1={PAD.top + ih} y2={PAD.top + ih} stroke={AXIS_COLOR} />
      {/* y ticks */}
      {yTicks.map(t => (
        <text key={t} x={PAD.left - 6} y={toY(t) + 4} textAnchor="end" fontSize={10} fill={TEXT_COLOR}>{formatNum(t)}</text>
      ))}
      {/* x ticks (sparse) */}
      {allX.filter((_, i) => i === 0 || i === allX.length - 1 || allX.length <= 6 || i % Math.ceil(allX.length / 5) === 0).map((x, i) => (
        <text key={i} x={toX(x)} y={PAD.top + ih + 14} textAnchor="middle" fontSize={9} fill={TEXT_COLOR}>
          {x.slice(0, 10)}
        </text>
      ))}
      {/* series */}
      {series.map((ser, si) => {
        const pts = ser.points;
        if (pts.length < 2) {
          return pts.map((p, i) => (
            <circle key={i} cx={toX(p.x)} cy={toY(p.y)} r={4} fill={ser.color} />
          ));
        }
        const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${toX(p.x)},${toY(p.y)}`).join(' ');
        return (
          <g key={si}>
            <path d={d} fill="none" stroke={ser.color} strokeWidth={2} />
            {pts.map((p, i) => (
              <circle key={i} cx={toX(p.x)} cy={toY(p.y)} r={4} fill={ser.color}>
                <title>{`${ser.label}\n${p.x.slice(0, 16)}: ${formatNum(p.y)}`}</title>
              </circle>
            ))}
          </g>
        );
      })}
      {/* legend */}
      {series.map((ser, i) => (
        <g key={i} transform={`translate(${PAD.left + i * 140}, ${h - 10})`}>
          <rect x={0} y={-8} width={12} height={8} fill={ser.color} />
          <text x={16} y={0} fontSize={10} fill={TEXT_COLOR}>{ser.label}</text>
        </g>
      ))}
      {yLabel && <text x={14} y={PAD.top + ih / 2} textAnchor="middle" fontSize={11} fill={TEXT_COLOR} transform={`rotate(-90, 14, ${PAD.top + ih / 2})`}>{yLabel}</text>}
    </svg>
  );
}

// ── Heatmap (seam quality grid) ───────────────────────────────────────────────

export interface HeatmapCell { col: string; row: string; value: number; color: string; label?: string; }

interface HeatmapProps { cells: HeatmapCell[]; cols: string[]; rows: string[]; title?: string; }

export function Heatmap({ cells, cols, rows, title }: HeatmapProps) {
  const cellW = 80, cellH = 28;
  const labelW = 160;
  const w = labelW + cols.length * cellW + 20;
  const h = 50 + rows.length * cellH;
  const cellMap = new Map(cells.map(c => [`${c.row}||${c.col}`, c]));

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} className="overflow-visible">
      {title && <text x={w / 2} y={14} textAnchor="middle" fontSize={12} fontWeight={600} fill={TEXT_COLOR}>{title}</text>}
      {cols.map((col, ci) => (
        <text key={ci} x={labelW + ci * cellW + cellW / 2} y={34}
          textAnchor="middle" fontSize={9} fill={TEXT_COLOR}>
          {col.length > 10 ? col.slice(0, 9) + '…' : col}
        </text>
      ))}
      {rows.map((row, ri) => (
        <g key={ri}>
          <text x={labelW - 4} y={50 + ri * cellH + cellH * 0.65}
            textAnchor="end" fontSize={9} fill={TEXT_COLOR}>
            {row.length > 18 ? row.slice(0, 17) + '…' : row}
          </text>
          {cols.map((col, ci) => {
            const cell = cellMap.get(`${row}||${col}`);
            const fillColor = cell?.color ?? '#1f2937';
            return (
              <g key={ci}>
                <rect x={labelW + ci * cellW} y={50 + ri * cellH}
                  width={cellW - 2} height={cellH - 2}
                  fill={fillColor} rx={3}>
                  <title>{`${row} / ${col}: ${cell?.label ?? 'N/A'}`}</title>
                </rect>
                {cell && (
                  <text x={labelW + ci * cellW + cellW / 2} y={50 + ri * cellH + cellH * 0.65}
                    textAnchor="middle" fontSize={8} fill="#fff" fontWeight={600}>
                    {cell.label ?? (cell.value * 100).toFixed(0) + '%'}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      ))}
    </svg>
  );
}

// ── Legend ────────────────────────────────────────────────────────────────────

export function Legend({ items }: { items: Array<{ color: string; label: string }> }) {
  return (
    <div className="flex flex-wrap gap-4 text-xs text-gray-400 mt-2">
      {items.map((it, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-sm" style={{ background: it.color }} />
          <span>{it.label}</span>
        </div>
      ))}
    </div>
  );
}
