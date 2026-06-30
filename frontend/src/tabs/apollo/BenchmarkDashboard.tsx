import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import {
  BarChart3, RefreshCw, Loader2, AlertCircle,
  TrendingUp, Cpu, Database, Activity, Zap, Eye, Download,
} from 'lucide-react';
import {
  BarChart, HBarChart, ScatterPlot, LineChart, Heatmap, Legend,
  type BarSeries, type ScatterDatum, type HeatmapCell,
} from './charts';
import {
  computeEfficiency, computeMemoryVsTimeScatter, computeMemoryBreakdown,
  computeSeamQualityHeatmap,
  verdictSummary, extractGeneralTrend, extractAspTrend, computeSuiteStats,
  timeVariancePct,
  computeAlignmentDrift, computePhotometricProfile, computePerSeamDetail,
  computeEdgeQualityBreakdown, computeFrameSelectionStats,
  computeFallbackReasonDistribution, computeGtComparisons,
  type BenchmarkReport, type GeneralBenchmark,
} from '../../math/benchmark';
import { applyColormapHex } from '../../math/colormap';

// ── Shared UI primitives ──────────────────────────────────────────────────────

const CARD = 'bg-gray-800 border border-gray-700 rounded-xl p-4';
const SECTION = 'text-lg font-semibold text-gray-100 mb-3';
const LABEL = 'text-xs text-gray-400 uppercase tracking-wide';
const VALUE = 'text-2xl font-bold text-white';
const TAB_BTN = (active: boolean) =>
  `px-3 py-1.5 text-sm rounded-md transition ${active
    ? 'bg-violet-600 text-white'
    : 'text-gray-400 hover:text-white hover:bg-gray-700'}`;

function MetricCard({ label, value, sub, good }: { label: string; value: string; sub?: string; good?: boolean }) {
  return (
    <div className={CARD}>
      <div className={LABEL}>{label}</div>
      <div className={`${VALUE} ${good === true ? 'text-green-400' : good === false ? 'text-red-400' : ''}`}>{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-0.5">{sub}</div>}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h3 className={SECTION}>{title}</h3>
      {children}
    </div>
  );
}

function Empty({ msg }: { msg: string }) {
  return (
    <div className="flex items-center justify-center h-32 text-gray-500 text-sm">
      <AlertCircle size={16} className="mr-2" /> {msg}
    </div>
  );
}

// ── Suite selector helpers ────────────────────────────────────────────────────

function suiteNames(reports: BenchmarkReport[]): string[] {
  return [...new Set(reports
    .filter((r): r is Extract<BenchmarkReport, { kind: 'General' }> => r.kind === 'General')
    .map(r => r.suite_name))].sort();
}

function latestSuiteReport(reports: BenchmarkReport[], name: string) {
  return (reports as Array<Extract<BenchmarkReport, { kind: 'General' }>>)
    .filter(r => r.kind === 'General' && r.suite_name === name)[0];
}

function aspReports(reports: BenchmarkReport[]): Array<Extract<BenchmarkReport, { kind: 'Asp' }>> {
  return reports.filter((r): r is Extract<BenchmarkReport, { kind: 'Asp' }> => r.kind === 'Asp');
}

// ── Overview page ─────────────────────────────────────────────────────────────

function OverviewPage({ reports }: { reports: BenchmarkReport[] }) {
  const suites = suiteNames(reports);
  const aspReps = aspReports(reports);
  const latestAsp = aspReps[0];

  return (
    <div className="space-y-6">
      {/* General suite summary cards */}
      {suites.length > 0 && (
        <Section title="General Benchmark Suites">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {suites.map(suite => {
              const r = latestSuiteReport(reports, suite);
              if (!r) return null;
              return (
                <MetricCard
                  key={suite}
                  label={suite}
                  value={`${r.summary.total_execution_time_sec.toFixed(2)}s`}
                  sub={`${r.summary.benchmarks_passed} benchmarks`}
                />
              );
            })}
          </div>
        </Section>
      )}

      {/* ASP summary cards */}
      {latestAsp && (
        <Section title="Anime Stitch Pipeline — Latest Run">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard label="Datasets" value={String(latestAsp.summary.total_datasets)} />
            <MetricCard label="Fallbacks" value={String(latestAsp.summary.datasets_fallback)}
              good={latestAsp.summary.datasets_fallback === 0} />
            <MetricCard label="Total Time" value={`${latestAsp.summary.total_time_sec.toFixed(1)}s`} />
            <MetricCard label="Avg/Dataset" value={`${latestAsp.summary.avg_time_per_dataset_sec.toFixed(1)}s`} />
            {latestAsp.summary.avg_sharpness_asp != null && (
              <MetricCard label="Avg Sharpness (ASP)" value={latestAsp.summary.avg_sharpness_asp.toFixed(1)}
                good={latestAsp.summary.avg_sharpness_asp > (latestAsp.summary.avg_sharpness_simple ?? 0)} />
            )}
            {latestAsp.summary.avg_sharpness_simple != null && (
              <MetricCard label="Avg Sharpness (Simple)" value={latestAsp.summary.avg_sharpness_simple.toFixed(1)} />
            )}
            {latestAsp.summary.avg_coverage_asp != null && (
              <MetricCard label="Avg Coverage (ASP)" value={(latestAsp.summary.avg_coverage_asp * 100).toFixed(1) + '%'} />
            )}
            {latestAsp.summary.verdict_counts && (
              <MetricCard label="ASP Better / Comparable"
                value={`${latestAsp.summary.verdict_counts['asp_better'] ?? 0} / ${latestAsp.summary.verdict_counts['comparable'] ?? 0}`}
                sub={`Simple better: ${latestAsp.summary.verdict_counts['simple_better'] ?? 0}`} />
            )}
          </div>
          {/* Verdict pie */}
          {latestAsp.summary.verdict_counts && (
            <div className={CARD}>
              <VerdictBar counts={latestAsp.summary.verdict_counts} />
            </div>
          )}
        </Section>
      )}

      {/* Performance insights from latest general suite */}
      {suites.map(suite => {
        const r = latestSuiteReport(reports, suite);
        if (!r) return null;
        const stats = computeSuiteStats(r.benchmarks);
        if (!stats) return null;
        return (
          <div key={suite} className={CARD}>
            <div className="font-semibold text-gray-200 mb-3">⚡ {suite} — Insights</div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-green-400 font-medium">Fastest: {stats.fastest.name}</div>
                <div className="text-gray-400">{stats.fastest.time.avg_sec.toFixed(4)}s</div>
                <div className="text-amber-400 font-medium mt-2">Slowest: {stats.slowest.name}</div>
                <div className="text-gray-400">{stats.slowest.time.avg_sec.toFixed(4)}s</div>
              </div>
              <div>
                <div className="text-green-400 font-medium">Least Memory: {stats.most_mem_efficient.name}</div>
                <div className="text-gray-400">{stats.most_mem_efficient.memory.avg_peak_mb.toFixed(1)} MB</div>
                <div className="text-amber-400 font-medium mt-2">Most Memory: {stats.most_mem_intensive.name}</div>
                <div className="text-gray-400">{stats.most_mem_intensive.memory.avg_peak_mb.toFixed(1)} MB</div>
              </div>
            </div>
            {stats.leaky.length > 0 && (
              <div className="mt-3 p-2 bg-red-900/30 border border-red-700 rounded text-sm">
                <span className="text-red-400 font-medium">⚠ Memory leaks (&gt;10 MB):</span>
                {stats.leaky.map(b => (
                  <div key={b.name} className="text-red-300 text-xs mt-0.5">
                    {b.name}: {b.memory.max_leaked_mb.toFixed(2)} MB leaked
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}

      {reports.length === 0 && (
        <Empty msg="No benchmark reports found. Run benchmarks with --save flag." />
      )}
    </div>
  );
}

function VerdictBar({ counts }: { counts: Record<string, number> }) {
  const asp = counts['asp_better'] ?? 0;
  const sim = counts['simple_better'] ?? 0;
  const comp = counts['comparable'] ?? 0;
  const total = asp + sim + comp || 1;
  return (
    <div>
      <div className="text-xs text-gray-400 mb-2">Verdict distribution (ASP vs Simple Stitch)</div>
      <div className="flex h-6 rounded overflow-hidden text-xs font-medium">
        {asp > 0 && <div style={{ width: `${(asp / total) * 100}%`, background: '#22c55e' }} className="flex items-center justify-center text-white">{asp}</div>}
        {comp > 0 && <div style={{ width: `${(comp / total) * 100}%`, background: '#6366f1' }} className="flex items-center justify-center text-white">{comp}</div>}
        {sim > 0 && <div style={{ width: `${(sim / total) * 100}%`, background: '#f59e0b' }} className="flex items-center justify-center text-white">{sim}</div>}
      </div>
      <Legend items={[
        { color: '#22c55e', label: `ASP better (${asp})` },
        { color: '#6366f1', label: `Comparable (${comp})` },
        { color: '#f59e0b', label: `Simple better (${sim})` },
      ]} />
    </div>
  );
}

// ── Suite Analysis page ───────────────────────────────────────────────────────

function SuiteAnalysisPage({ reports }: { reports: BenchmarkReport[] }) {
  const suites = suiteNames(reports);
  const [selected, setSelected] = useState(suites[0] ?? '');

  const r = useMemo(() => selected ? latestSuiteReport(reports, selected) : undefined, [reports, selected]);
  const benchmarks = r?.benchmarks ?? [];

  const timeLabels = benchmarks.map(b => b.name);
  const timeSeries: BarSeries[] = [{
    label: 'Avg Time',
    color: '#4ade80',
    values: benchmarks.map(b => b.time.avg_sec),
    errorPlus: benchmarks.map(b => b.time.max_sec - b.time.avg_sec),
    errorMinus: benchmarks.map(b => b.time.avg_sec - b.time.min_sec),
  }];
  const memSeries: BarSeries[] = [
    { label: 'Avg Peak', color: '#60a5fa', values: benchmarks.map(b => b.memory.avg_peak_mb) },
    { label: 'Max Peak', color: '#f97316', values: benchmarks.map(b => b.memory.max_peak_mb) },
  ];

  const [activeTab, setActiveTab] = useState<'time' | 'memory' | 'table'>('time');

  return (
    <div className="space-y-4">
      <div className="flex gap-3 items-center">
        <select value={selected} onChange={e => setSelected(e.target.value)}
          className="bg-gray-700 text-white text-sm rounded-lg border border-gray-600 px-3 py-1.5 focus:ring-violet-500 focus:border-violet-500">
          {suites.map(s => <option key={s}>{s}</option>)}
        </select>
      </div>

      {!r ? (
        <Empty msg="Select a benchmark suite." />
      ) : (
        <>
          <div className="grid grid-cols-4 gap-3">
            <MetricCard label="Last Run" value={r.system.timestamp.slice(0, 10)} />
            <MetricCard label="Benchmarks" value={String(r.benchmarks.length)} />
            <MetricCard label="Total Time" value={`${r.summary.total_execution_time_sec.toFixed(2)}s`} />
            <MetricCard label="Peak Memory" value={`${r.summary.max_peak_memory_mb.toFixed(0)} MB`} />
          </div>

          {/* System info */}
          <details className={CARD}>
            <summary className="cursor-pointer text-sm text-gray-300 font-medium">System Information</summary>
            <div className="grid grid-cols-2 gap-2 mt-3 text-sm text-gray-400">
              <div>Platform: {r.system.platform}</div>
              <div>CPU: {r.system.cpu}</div>
              <div>Threads: {r.system.cpu_threads ?? 'N/A'}</div>
              <div>RAM: {r.system.ram_gb ? `${r.system.ram_gb} GB` : 'N/A'}</div>
              <div>GPU: {r.system.gpu ?? 'N/A'}</div>
              {r.system.cuda_version && <div>CUDA: {r.system.cuda_version}</div>}
            </div>
          </details>

          <div className="flex gap-2">
            {(['time', 'memory', 'table'] as const).map(t => (
              <button key={t} className={TAB_BTN(activeTab === t)} onClick={() => setActiveTab(t)}>
                {t === 'time' ? '⏱ Time' : t === 'memory' ? '💾 Memory' : '📋 Table'}
              </button>
            ))}
          </div>

          <div className={CARD}>
            {activeTab === 'time' && benchmarks.length > 0 && (
              <BarChart labels={timeLabels} series={timeSeries} yLabel="Time (s)" xLabel="Benchmark"
                title={`${selected} — Execution Time`} height={320} />
            )}
            {activeTab === 'memory' && benchmarks.length > 0 && (
              <BarChart labels={timeLabels} series={memSeries} yLabel="Memory (MB)" xLabel="Benchmark"
                title={`${selected} — Memory Usage`} height={320} />
            )}
            {activeTab === 'table' && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-gray-300">
                  <thead className="text-xs text-gray-400 border-b border-gray-700">
                    <tr>
                      {['Benchmark', 'Iters', 'Avg (s)', 'Min (s)', 'Max (s)', 'Var%', 'Peak (MB)', 'Delta (MB)', 'Leaked (MB)'].map(h => (
                        <th key={h} className="text-left py-2 pr-4">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {benchmarks.map(b => (
                      <tr key={b.name} className="border-b border-gray-700/50 hover:bg-gray-700/30">
                        <td className="py-1.5 pr-4 font-mono text-xs">{b.name}</td>
                        <td className="pr-4">{b.iterations}</td>
                        <td className="pr-4">{b.time.avg_sec.toFixed(4)}</td>
                        <td className="pr-4">{b.time.min_sec.toFixed(4)}</td>
                        <td className="pr-4">{b.time.max_sec.toFixed(4)}</td>
                        <td className="pr-4">{timeVariancePct(b).toFixed(1)}%</td>
                        <td className="pr-4">{b.memory.avg_peak_mb.toFixed(1)}</td>
                        <td className="pr-4">{b.memory.avg_delta_mb.toFixed(1)}</td>
                        <td className={b.memory.max_leaked_mb > 5 ? 'text-red-400 pr-4' : 'pr-4'}>
                          {b.memory.max_leaked_mb.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <button onClick={() => {
                  const csv = [
                    'Benchmark,Iters,Avg(s),Min(s),Max(s),Var%,Peak(MB),Delta(MB),Leaked(MB)',
                    ...benchmarks.map(b => `${b.name},${b.iterations},${b.time.avg_sec},${b.time.min_sec},${b.time.max_sec},${timeVariancePct(b).toFixed(1)},${b.memory.avg_peak_mb},${b.memory.avg_delta_mb},${b.memory.max_leaked_mb}`)
                  ].join('\n');
                  const a = document.createElement('a');
                  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
                  a.download = `${selected}_benchmarks.csv`;
                  a.click();
                }} className="mt-3 flex items-center gap-1.5 text-xs text-violet-400 hover:text-violet-300">
                  <Download size={14} /> Download CSV
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ── Function Comparison page ──────────────────────────────────────────────────

function FunctionComparisonPage({ reports }: { reports: BenchmarkReport[] }) {
  const suites = ['All Suites', ...suiteNames(reports)];
  const [selected, setSelected] = useState('All Suites');
  const [activeTab, setActiveTab] = useState<'scatter' | 'ranking' | 'throughput' | 'memory' | 'table' | 'recommendations'>('scatter');

  const benchmarks = useMemo((): GeneralBenchmark[] => {
    if (selected === 'All Suites') {
      return suiteNames(reports).flatMap(s => {
        const r = latestSuiteReport(reports, s);
        return r ? r.benchmarks.map(b => ({ ...b, name: `[${s}] ${b.name}` })) : [];
      });
    }
    return latestSuiteReport(reports, selected)?.benchmarks ?? [];
  }, [reports, selected]);

  const efficiency = useMemo(() => computeEfficiency(benchmarks), [benchmarks]);
  const scatter = useMemo(() => computeMemoryVsTimeScatter(benchmarks), [benchmarks]);
  const breakdown = useMemo(() => computeMemoryBreakdown(benchmarks), [benchmarks]);

  const scatterData: ScatterDatum[] = scatter.map(s => ({
    x: s.x, y: s.y, r: s.r, color: s.color,
    label: s.name, tooltip: `${s.name}\nTime: ${s.x.toFixed(4)}s\nMem: ${s.y.toFixed(1)} MB\nEfficiency: ${s.efficiency.toFixed(1)}`,
  }));

  const avgTime = benchmarks.reduce((s, b) => s + b.time.avg_sec, 0) / (benchmarks.length || 1);
  const peakMem = Math.max(...benchmarks.map(b => b.memory.avg_peak_mb), 0);
  const totalLeaked = benchmarks.reduce((s, b) => s + b.memory.max_leaked_mb, 0);

  const highTime = benchmarks.filter(b => b.time.avg_sec > avgTime * 1.5);
  const highMem = benchmarks.filter(b => b.memory.avg_peak_mb > peakMem * 0.7);

  const tabs = ['scatter', 'ranking', 'throughput', 'memory', 'table', 'recommendations'] as const;
  const tabLabels: Record<typeof tabs[number], string> = {
    scatter: '📈 Memory vs Time', ranking: '🏆 Ranking', throughput: '⚡ Throughput',
    memory: '💾 Memory', table: '📋 Table', recommendations: '💡 Recommendations',
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-3 items-center">
        <select value={selected} onChange={e => setSelected(e.target.value)}
          className="bg-gray-700 text-white text-sm rounded-lg border border-gray-600 px-3 py-1.5">
          {suites.map(s => <option key={s}>{s}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <MetricCard label="Total Time" value={`${benchmarks.reduce((s, b) => s + b.time.total_sec, 0).toFixed(2)}s`} />
        <MetricCard label="Avg Time" value={`${avgTime.toFixed(4)}s`} />
        <MetricCard label="Peak Memory" value={`${peakMem.toFixed(0)} MB`} />
        <MetricCard label="Total Leaked" value={`${totalLeaked.toFixed(2)} MB`} good={totalLeaked < 5} />
      </div>

      <div className="flex flex-wrap gap-2">
        {tabs.map(t => (
          <button key={t} className={TAB_BTN(activeTab === t)} onClick={() => setActiveTab(t)}>
            {tabLabels[t]}
          </button>
        ))}
      </div>

      <div className={CARD}>
        {activeTab === 'scatter' && (
          <>
            <p className="text-xs text-gray-400 mb-3">Bubble size = efficiency score (larger = less efficient). Ideal = bottom-left.</p>
            <ScatterPlot data={scatterData} xLabel="Avg Time (s)" yLabel="Avg Peak Memory (MB)"
              title="Memory vs Execution Time" height={400} logX={scatterData.length > 2} />
          </>
        )}
        {activeTab === 'ranking' && (
          <>
            <p className="text-xs text-gray-400 mb-3">Combined efficiency (time + memory normalised). Lower = better.</p>
            <HBarChart
              data={efficiency.map(e => ({ name: e.name, value: e.score, color: e.color }))}
              xLabel="Efficiency Score (lower = better)"
              title="Benchmark Efficiency Ranking" />
            <div className="grid grid-cols-2 gap-4 mt-4 text-sm">
              <div>
                <div className="text-green-400 font-medium mb-1">🏆 Most Efficient</div>
                {efficiency.slice(0, 3).map((e, i) => (
                  <div key={e.name} className="text-gray-300">
                    {i + 1}. {e.name} <span className="text-gray-500">({e.score.toFixed(1)})</span>
                  </div>
                ))}
              </div>
              <div>
                <div className="text-red-400 font-medium mb-1">⚠ Needs Optimisation</div>
                {[...efficiency].reverse().slice(0, 3).map((e, i) => (
                  <div key={e.name} className="text-gray-300">
                    {i + 1}. {e.name} <span className="text-gray-500">({e.score.toFixed(1)})</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
        {activeTab === 'throughput' && (
          <>
            <BarChart
              labels={benchmarks.map(b => b.name)}
              series={[{ label: 'Throughput', color: '#a78bfa', values: efficiency.map(e => e.throughput) }]}
              yLabel="ops/sec" xLabel="Benchmark" title="Benchmark Throughput" height={300} />
            {efficiency.length > 0 && (
              <div className="text-sm text-gray-300 mt-2">
                Highest: <span className="text-violet-400">{efficiency.sort((a, b) => b.throughput - a.throughput)[0]?.name}</span>
              </div>
            )}
          </>
        )}
        {activeTab === 'memory' && (
          <>
            <p className="text-xs text-gray-400 mb-3">Stacked: baseline + operation delta + leaked.</p>
            <BarChart
              labels={breakdown.map(d => d.name)}
              series={[
                { label: 'Baseline', color: '#60a5fa', values: breakdown.map(d => d.baseline) },
                { label: 'Delta', color: '#fbbf24', values: breakdown.map(d => d.delta) },
                { label: 'Leaked', color: '#f87171', values: breakdown.map(d => d.leaked) },
              ]}
              stacked yLabel="Memory (MB)" xLabel="Benchmark" title="Memory Breakdown" height={320} />
            <Legend items={[
              { color: '#60a5fa', label: 'Baseline' },
              { color: '#fbbf24', label: 'Operation Delta' },
              { color: '#f87171', label: 'Leaked' },
            ]} />
            {benchmarks.filter(b => b.memory.max_leaked_mb > 5).length > 0 && (
              <div className="mt-3 p-2 bg-red-900/30 border border-red-700 rounded text-xs text-red-300">
                ⚠ {benchmarks.filter(b => b.memory.max_leaked_mb > 5).length} benchmark(s) with &gt;5 MB leak
              </div>
            )}
          </>
        )}
        {activeTab === 'table' && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-gray-300">
              <thead className="text-gray-400 border-b border-gray-700">
                <tr>
                  {['Function', 'Avg (s)', 'Var%', 'ops/s', 'Mem (MB)', 'Delta (MB)', 'Leaked (MB)', 'Iters'].map(h => (
                    <th key={h} className="text-left py-2 pr-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {benchmarks.map(b => {
                  const thr = b.time.total_sec > 0 ? b.iterations / b.time.total_sec : 0;
                  return (
                    <tr key={b.name} className="border-b border-gray-700/40 hover:bg-gray-700/20">
                      <td className="py-1 pr-3 font-mono">{b.name}</td>
                      <td className="pr-3">{b.time.avg_sec.toFixed(4)}</td>
                      <td className="pr-3">{timeVariancePct(b).toFixed(1)}</td>
                      <td className="pr-3">{thr.toFixed(2)}</td>
                      <td className="pr-3">{b.memory.avg_peak_mb.toFixed(1)}</td>
                      <td className="pr-3">{b.memory.avg_delta_mb.toFixed(1)}</td>
                      <td className={`pr-3 ${b.memory.max_leaked_mb > 5 ? 'text-red-400' : ''}`}>{b.memory.max_leaked_mb.toFixed(2)}</td>
                      <td>{b.iterations}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {activeTab === 'recommendations' && (
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-amber-400 font-medium mb-2">⏱ Time Targets</div>
              {highTime.length === 0
                ? <div className="text-green-400 text-xs">All within acceptable range.</div>
                : highTime.map(b => (
                  <div key={b.name} className="text-amber-300 text-xs mb-1">
                    {b.name}: {b.time.avg_sec.toFixed(4)}s (&gt;{(avgTime * 1.5).toFixed(4)}s threshold)
                  </div>
                ))}
            </div>
            <div>
              <div className="text-amber-400 font-medium mb-2">💾 Memory Targets</div>
              {highMem.length === 0
                ? <div className="text-green-400 text-xs">All within acceptable range.</div>
                : highMem.map(b => (
                  <div key={b.name} className="text-amber-300 text-xs mb-1">
                    {b.name}: {b.memory.avg_peak_mb.toFixed(0)} MB
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Benchmark Trends page ─────────────────────────────────────────────────────

function TrendsPage({ reports }: { reports: BenchmarkReport[] }) {
  const suites = suiteNames(reports);
  const aspReps = aspReports(reports);
  const [mode, setMode] = useState<'general' | 'asp'>(suites.length > 0 ? 'general' : 'asp');
  const [selectedSuite, setSelectedSuite] = useState(suites[0] ?? '');
  const [selectedBench, setSelectedBench] = useState('');
  const [selectedDataset, setSelectedDataset] = useState('');
  const [aspField, setAspField] = useState<'total_sec' | 'composite_sec' | 'matching_sec' | 'sharpness' | 'composite_quality'>('total_sec');

  const allBenches = useMemo(() => {
    const rs = (reports as Array<Extract<BenchmarkReport, { kind: 'General' }>>)
      .filter(r => r.kind === 'General' && r.suite_name === selectedSuite);
    return [...new Set(rs.flatMap(r => r.benchmarks.map(b => b.name)))].sort();
  }, [reports, selectedSuite]);

  const allDatasets = useMemo(() => {
    return [...new Set(aspReps.flatMap(r => r.datasets.map(d => d.name)))].sort();
  }, [aspReps]);

  useEffect(() => { if (allBenches.length > 0) setSelectedBench(allBenches[0]); }, [allBenches]);
  useEffect(() => { if (allDatasets.length > 0) setSelectedDataset(allDatasets[0]); }, [allDatasets]);

  const trendData = useMemo(() => {
    if (mode === 'general') {
      const t = extractGeneralTrend(reports, selectedSuite, selectedBench, 'avg_sec');
      const m = extractGeneralTrend(reports, selectedSuite, selectedBench, 'avg_peak_mb');
      return { time: t, mem: m };
    }
    const t = extractAspTrend(reports, selectedDataset, aspField);
    return { time: t, mem: [] };
  }, [reports, mode, selectedSuite, selectedBench, selectedDataset, aspField]);

  const hasTime = trendData.time.length >= 2;

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {suites.length > 0 && <button className={TAB_BTN(mode === 'general')} onClick={() => setMode('general')}>General Suites</button>}
        {aspReps.length > 0 && <button className={TAB_BTN(mode === 'asp')} onClick={() => setMode('asp')}>ASP Pipeline</button>}
      </div>

      {mode === 'general' && (
        <div className="flex gap-3">
          <select value={selectedSuite} onChange={e => setSelectedSuite(e.target.value)}
            className="bg-gray-700 text-white text-sm rounded-lg border border-gray-600 px-3 py-1.5">
            {suites.map(s => <option key={s}>{s}</option>)}
          </select>
          <select value={selectedBench} onChange={e => setSelectedBench(e.target.value)}
            className="bg-gray-700 text-white text-sm rounded-lg border border-gray-600 px-3 py-1.5">
            {allBenches.map(b => <option key={b}>{b}</option>)}
          </select>
        </div>
      )}

      {mode === 'asp' && (
        <div className="flex gap-3">
          <select value={selectedDataset} onChange={e => setSelectedDataset(e.target.value)}
            className="bg-gray-700 text-white text-sm rounded-lg border border-gray-600 px-3 py-1.5">
            {allDatasets.map(d => <option key={d}>{d}</option>)}
          </select>
          <select value={aspField} onChange={e => setAspField(e.target.value as any)}
            className="bg-gray-700 text-white text-sm rounded-lg border border-gray-600 px-3 py-1.5">
            {[['total_sec', 'Total time (s)'], ['composite_sec', 'Composite (s)'], ['matching_sec', 'Matching (s)'], ['sharpness', 'ASP Sharpness'], ['composite_quality', 'Composite Quality']].map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </div>
      )}

      {!hasTime ? (
        <Empty msg="Need at least 2 benchmark runs to show trends." />
      ) : (
        <div className={CARD}>
          <LineChart
            series={[
              { label: mode === 'general' ? 'Time (s)' : String(aspField), color: '#4ade80', points: trendData.time.map(p => ({ x: p.timestamp, y: p.value })) },
              ...(trendData.mem.length >= 2 ? [{ label: 'Memory (MB)', color: '#60a5fa', points: trendData.mem.map(p => ({ x: p.timestamp, y: p.value })) }] : []),
            ]}
            title={mode === 'general' ? `Trend: ${selectedBench}` : `ASP Trend: ${selectedDataset} / ${aspField}`}
            height={280} />
        </div>
      )}

      {/* Historical table */}
      {trendData.time.length > 0 && (
        <div className={CARD}>
          <div className="font-medium text-gray-300 text-sm mb-2">Historical Data</div>
          <table className="w-full text-xs text-gray-300">
            <thead className="text-gray-400 border-b border-gray-700">
              <tr>
                <th className="text-left py-1 pr-4">Timestamp</th>
                <th className="text-left py-1 pr-4">Value</th>
                <th className="text-left py-1">File</th>
              </tr>
            </thead>
            <tbody>
              {[...trendData.time].reverse().map((p, i) => (
                <tr key={i} className="border-b border-gray-700/40">
                  <td className="py-1 pr-4">{p.timestamp.slice(0, 19)}</td>
                  <td className="pr-4">{p.value.toFixed(4)}</td>
                  <td className="font-mono text-gray-500">{p.file_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── ASP Pipeline Analysis page ────────────────────────────────────────────────

type AspTab = 'overview' | 'timing' | 'seam' | 'per-seam' | 'alignment' | 'photometric' | 'edge' | 'frames' | 'fallback' | 'gt' | 'comparison' | 'heatmap';

const ASP_TABS: Array<{ id: AspTab; label: string }> = [
  { id: 'overview', label: '📋 Overview' },
  { id: 'timing', label: '⏱ Timing' },
  { id: 'seam', label: '📏 Seam Quality' },
  { id: 'per-seam', label: '🔍 Per-Seam' },
  { id: 'alignment', label: '📐 Alignment' },
  { id: 'photometric', label: '🌅 Photometric' },
  { id: 'edge', label: '🔗 Edge Quality' },
  { id: 'frames', label: '🎞 Frame Selection' },
  { id: 'fallback', label: '⚠ Fallback Root Cause' },
  { id: 'gt', label: '🎯 GT Comparison' },
  { id: 'comparison', label: '⚖ ASP vs Simple' },
  { id: 'heatmap', label: '🌡 Heatmap' },
];

function AspAnalysisPage({ reports }: { reports: BenchmarkReport[] }) {
  const aspReps = aspReports(reports);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [activeTab, setActiveTab] = useState<AspTab>('overview');

  const r = aspReps[selectedIdx];
  const datasets = useMemo(() => r?.datasets ?? [], [r]);

  const heatRows = useMemo(() => computeSeamQualityHeatmap(datasets), [datasets]);
  const heatCols = useMemo(() => ['Composite Quality', 'NCC', 'Color Sim', 'Anti-Ghost', 'Seam Vis', 'RLHF'], []);
  const heatCells = useMemo((): HeatmapCell[] => {
    const fields: Array<keyof typeof heatRows[0]> = ['composite_quality', 'seam_ncc_min', 'seam_color_min', 'ghosting_siqe_norm', 'seam_visibility_norm', 'rlhf_score'];
    return heatRows.flatMap(row => {
      const colors = applyColormapHex(fields.map(f => row[f] as number), 'viridis');
      return fields.map((f, fi) => ({
        row: row.dataset,
        col: heatCols[fi],
        value: row[f] as number,
        color: colors[fi],
        label: ((row[f] as number) * 100).toFixed(0) + '%',
      }));
    });
  }, [heatRows, heatCols]);

  const verdicts = useMemo(() => verdictSummary(datasets), [datasets]);
  const alignmentDrift = useMemo(() => computeAlignmentDrift(datasets), [datasets]);
  const photometricData = useMemo(() => computePhotometricProfile(datasets), [datasets]);
  const perSeamData = useMemo(() => computePerSeamDetail(datasets), [datasets]);
  const edgeQuality = useMemo(() => computeEdgeQualityBreakdown(datasets), [datasets]);
  const frameSelection = useMemo(() => computeFrameSelectionStats(datasets), [datasets]);
  const fallbackReasons = useMemo(() => computeFallbackReasonDistribution(datasets), [datasets]);
  const gtComparisons = useMemo(() => computeGtComparisons(datasets), [datasets]);

  return (
    <div className="space-y-4">
      <div className="flex gap-3 items-center">
        <select value={selectedIdx} onChange={e => setSelectedIdx(Number(e.target.value))}
          className="bg-gray-700 text-white text-sm rounded-lg border border-gray-600 px-3 py-1.5">
          {aspReps.map((rr, i) => (
            <option key={i} value={i}>{rr.file_name.slice(0, 40)}</option>
          ))}
        </select>
      </div>

      {!r ? (
        <Empty msg="No ASP benchmark reports found." />
      ) : (
        <>
          <div className="grid grid-cols-4 gap-3">
            <MetricCard label="Datasets" value={String(r.summary.total_datasets)} />
            <MetricCard label="Fallbacks" value={String(r.summary.datasets_fallback)} good={r.summary.datasets_fallback === 0} />
            <MetricCard label="Total Time" value={`${r.summary.total_time_sec.toFixed(1)}s`} />
            <MetricCard label="Avg/Dataset" value={`${r.summary.avg_time_per_dataset_sec.toFixed(1)}s`} />
          </div>

          <div className="flex flex-wrap gap-2">
            {ASP_TABS.map(t => (
              <button key={t.id} className={TAB_BTN(activeTab === t.id)} onClick={() => setActiveTab(t.id)}>
                {t.label}
              </button>
            ))}
          </div>

          <div className={CARD}>
            {activeTab === 'overview' && (
              <div className="space-y-3">
                <VerdictBar counts={{ asp_better: verdicts.asp_better, simple_better: verdicts.simple_better, comparable: verdicts.comparable }} />
                <div className="overflow-x-auto mt-3">
                  <table className="w-full text-xs text-gray-300">
                    <thead className="text-gray-400 border-b border-gray-700">
                      <tr>
                        {['Dataset', 'Frames', 'Canvas', 'Total(s)', 'Mode', 'Sharpness', 'Coverage', 'CompQuality', 'Banding', 'Verdict'].map(h => (
                          <th key={h} className="text-left py-1.5 pr-3">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {datasets.map(ds => {
                        const verdict = (ds.comparison as any)?.verdict;
                        return (
                          <tr key={ds.name} className={`border-b border-gray-700/40 hover:bg-gray-700/20 ${ds.used_fallback ? 'opacity-60' : ''}`}>
                            <td className="py-1.5 pr-3 font-mono">{ds.name}</td>
                            <td className="pr-3">{ds.frame_count ?? '—'}</td>
                            <td className="pr-3">{ds.canvas_width && ds.canvas_height ? `${ds.canvas_width}×${ds.canvas_height}` : '—'}</td>
                            <td className="pr-3">{ds.time.total_sec.toFixed(1)}</td>
                            <td className={`pr-3 ${ds.used_fallback ? 'text-amber-400' : 'text-green-400'}`}>{ds.used_fallback ? 'SCANS' : 'ASP'}</td>
                            <td className="pr-3">{ds.metrics_asp?.sharpness?.toFixed(0) ?? '—'}</td>
                            <td className="pr-3">{ds.metrics_asp?.coverage != null ? (ds.metrics_asp.coverage * 100).toFixed(1) + '%' : '—'}</td>
                            <td className="pr-3">{ds.metrics_asp?.composite_quality?.toFixed(3) ?? '—'}</td>
                            <td className="pr-3">{ds.metrics_asp?.strip_banding_score?.toFixed(1) ?? '—'}</td>
                            <td className={verdict === 'asp_better' ? 'text-green-400' : verdict === 'simple_better' ? 'text-amber-400' : 'text-gray-400'}>
                              {verdict ?? '—'}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {activeTab === 'timing' && datasets.length > 0 && (
              <>
                <BarChart
                  labels={datasets.map(d => d.name)}
                  series={[
                    { label: 'BiRefNet', color: '#6366f1', values: datasets.map(d => d.time.birefnet_sec ?? 0) },
                    { label: 'Matching', color: '#8b5cf6', values: datasets.map(d => d.time.matching_sec ?? 0) },
                    { label: 'Composite', color: '#22c55e', values: datasets.map(d => d.time.composite_sec ?? 0) },
                    { label: 'Render', color: '#16a34a', values: datasets.map(d => d.time.render_sec ?? 0) },
                    { label: 'Bundle Adj', color: '#f59e0b', values: datasets.map(d => d.time.bundle_adjust_sec ?? 0) },
                  ]}
                  stacked yLabel="Time (s)" xLabel="Dataset" title="Pipeline Stage Timing" height={340} />
                <Legend items={[
                  { color: '#6366f1', label: 'BiRefNet' },
                  { color: '#8b5cf6', label: 'Matching' },
                  { color: '#22c55e', label: 'Composite' },
                  { color: '#16a34a', label: 'Render' },
                  { color: '#f59e0b', label: 'Bundle Adj' },
                ]} />
              </>
            )}

            {activeTab === 'seam' && (
              <div className="space-y-4">
                <BarChart
                  labels={datasets.map(d => d.name)}
                  series={[
                    { label: 'Composite Quality', color: '#6366f1', values: datasets.map(d => d.metrics_asp?.composite_quality ?? 0) },
                    { label: 'Seam NCC', color: '#22c55e', values: datasets.map(d => d.metrics_asp?.seam_ncc_min != null ? (d.metrics_asp.seam_ncc_min + 1) / 2 : 0) },
                    { label: 'Color Match', color: '#f59e0b', values: datasets.map(d => d.metrics_asp?.seam_color_min ?? 0) },
                  ]}
                  yLabel="Score (0–1, higher=better)" xLabel="Dataset" title="Per-Dataset Seam Quality" height={300} />
                <Legend items={[
                  { color: '#6366f1', label: 'Composite Quality' },
                  { color: '#22c55e', label: 'NCC Coherence' },
                  { color: '#f59e0b', label: 'Color Match' },
                ]} />
                <BarChart
                  labels={datasets.map(d => d.name)}
                  series={[
                    { label: 'Ghosting SIQE', color: '#f87171', values: datasets.map(d => d.metrics_asp?.ghosting_siqe ?? 0) },
                    { label: 'Seam Visibility', color: '#fb923c', values: datasets.map(d => d.metrics_asp?.seam_visibility ?? 0) },
                    { label: 'Strip Banding', color: '#fbbf24', values: datasets.map(d => d.metrics_asp?.strip_banding_score ?? 0) },
                    { label: 'Seam Coherence', color: '#a3e635', values: datasets.map(d => d.metrics_asp?.seam_coherence ?? 0) },
                  ]}
                  yLabel="Score (lower=better)" xLabel="Dataset" title="Artifact Metrics (lower = cleaner)" height={300} />
              </div>
            )}

            {activeTab === 'per-seam' && (
              <div className="space-y-4">
                <p className="text-xs text-gray-400">Per-seam breakdown: each bar group is one boundary between adjacent frames.</p>
                {perSeamData.length === 0
                  ? <Empty msg="No per-seam data — run benchmark with per-seam metric collection enabled." />
                  : (() => {
                      const dsNames = [...new Set(perSeamData.map(e => e.dataset))];
                      return dsNames.map(dsName => {
                        const entries = perSeamData.filter(e => e.dataset === dsName);
                        const labels = entries.map(e => `Seam ${e.seam_index}`);
                        return (
                          <div key={dsName} className="space-y-2">
                            <p className="text-xs font-semibold text-gray-300">{dsName}</p>
                            <BarChart
                              labels={labels}
                              series={[
                                { label: 'Ghost (0=clean,100=bad)', color: '#f87171', values: entries.map(e => e.ghost_score ?? 0) },
                                { label: 'NCC (norm 0–1, higher=better)', color: '#4ade80', values: entries.map(e => e.ncc_score != null ? (e.ncc_score + 1) / 2 : 0) },
                                { label: 'Color Sim (higher=better)', color: '#60a5fa', values: entries.map(e => e.color_score ?? 0) },
                              ]}
                              yLabel="Score" xLabel="Seam boundary" title={`Per-Seam Quality — ${dsName}`} height={220} />
                          </div>
                        );
                      });
                    })()
                }
              </div>
            )}

            {activeTab === 'alignment' && (
              <div className="space-y-4">
                <p className="text-xs text-gray-400">Alignment drift: dy_cv &gt; dx_cv → vertical scroll (normal). High CV = jitter.</p>
                {alignmentDrift.length === 0
                  ? <Empty msg="No alignment data in benchmark output. Check that ASP produces alignment block in JSON." />
                  : (
                    <>
                      <BarChart
                        labels={alignmentDrift.map(e => e.dataset)}
                        series={[
                          { label: 'dy CoeffVar (vertical)', color: '#6366f1', values: alignmentDrift.map(e => e.dy_cv) },
                          { label: 'dx CoeffVar (horizontal)', color: '#f59e0b', values: alignmentDrift.map(e => e.dx_cv) },
                        ]}
                        yLabel="Coeff. of Variation" xLabel="Dataset"
                        title="Scroll-Axis Jitter (CoV of per-frame steps — lower = more uniform scroll)" height={300} />
                      <Legend items={[
                        { color: '#6366f1', label: 'dy CoV (vertical scroll)' },
                        { color: '#f59e0b', label: 'dx CoV (horizontal scroll)' },
                      ]} />
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs text-gray-300">
                          <thead className="text-gray-400 border-b border-gray-700">
                            <tr>
                              {['Dataset', 'Scroll Axis', 'dy CoV', 'dx CoV', 'Fallback'].map(h => (
                                <th key={h} className="text-left py-1.5 pr-4">{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {alignmentDrift.map(e => (
                              <tr key={e.dataset} className="border-b border-gray-700/40 hover:bg-gray-700/20">
                                <td className="py-1.5 pr-4 font-mono">{e.dataset}</td>
                                <td className="pr-4">{e.is_horizontal_scroll ? 'Horizontal' : 'Vertical'}</td>
                                <td className="pr-4">{e.dy_cv.toFixed(3)}</td>
                                <td className="pr-4">{e.dx_cv.toFixed(3)}</td>
                                <td className={e.used_fallback ? 'text-amber-400' : 'text-green-400'}>{e.used_fallback ? 'SCANS' : 'ASP'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )
                }
              </div>
            )}

            {activeTab === 'photometric' && (
              <div className="space-y-4">
                <p className="text-xs text-gray-400">Per-frame gain applied during photometric normalisation. Gains far from 1.0 indicate brightness mismatch.</p>
                {photometricData.length === 0
                  ? <Empty msg="No photometric data in benchmark output." />
                  : (() => {
                      const dsNames = [...new Set(photometricData.map(e => e.dataset))];
                      return dsNames.map(dsName => {
                        const entries = photometricData.filter(e => e.dataset === dsName).sort((a, b) => a.frame_index - b.frame_index);
                        const labels = entries.map(e => `F${e.frame_index}`);
                        const refLum = entries[0]?.ref_lum;
                        return (
                          <div key={dsName} className="space-y-2">
                            <p className="text-xs font-semibold text-gray-300">{dsName}{refLum != null ? ` — ref lum: ${refLum.toFixed(1)}` : ''}</p>
                            <BarChart
                              labels={labels}
                              series={[
                                { label: 'Applied gain', color: '#6366f1', values: entries.map(e => e.applied_gain) },
                                { label: 'BG luminance /255', color: '#f59e0b', values: entries.map(e => e.bg_lum != null ? e.bg_lum / 255 : 0) },
                              ]}
                              yLabel="Value" xLabel="Frame"
                              title={`Photometric Correction — ${dsName}`} height={220} />
                          </div>
                        );
                      });
                    })()
                }
              </div>
            )}

            {activeTab === 'edge' && (
              <div className="space-y-4">
                <p className="text-xs text-gray-400">Affine health per dataset: ratio = inlier fraction, min_gap_px = smallest adjacent step.</p>
                {edgeQuality.length === 0
                  ? <Empty msg="No affine health data in benchmark output." />
                  : (
                    <>
                      <BarChart
                        labels={edgeQuality.map(e => e.dataset)}
                        series={[
                          { label: 'Inlier ratio', color: '#4ade80', values: edgeQuality.map(e => e.health_ratio) },
                        ]}
                        yLabel="Ratio (0–1)" xLabel="Dataset"
                        title="Affine Inlier Ratio (higher = more consistent edge set)" height={260} />
                      <BarChart
                        labels={edgeQuality.map(e => e.dataset)}
                        series={[
                          { label: 'Min gap (px)', color: '#60a5fa', values: edgeQuality.map(e => e.min_gap_px) },
                          { label: 'Max rotation (°×10)', color: '#f59e0b', values: edgeQuality.map(e => e.max_rotation * 10) },
                          { label: 'Max scale dev (%)', color: '#f87171', values: edgeQuality.map(e => e.max_scale_dev * 100) },
                        ]}
                        yLabel="Value" xLabel="Dataset"
                        title="Affine Geometry Diagnostics" height={260} />
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs text-gray-300">
                          <thead className="text-gray-400 border-b border-gray-700">
                            <tr>
                              {['Dataset', 'Valid', 'Ratio', 'Min Gap (px)', 'Max Rot (°)', 'Max Scale Dev', 'Reason', 'Fallback'].map(h => (
                                <th key={h} className="text-left py-1.5 pr-3">{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {edgeQuality.map(e => (
                              <tr key={e.dataset} className="border-b border-gray-700/40 hover:bg-gray-700/20">
                                <td className="py-1.5 pr-3 font-mono">{e.dataset}</td>
                                <td className={`pr-3 ${e.health_valid ? 'text-green-400' : 'text-red-400'}`}>{e.health_valid ? '✓' : '✗'}</td>
                                <td className="pr-3">{e.health_ratio.toFixed(3)}</td>
                                <td className="pr-3">{e.min_gap_px.toFixed(1)}</td>
                                <td className="pr-3">{e.max_rotation.toFixed(3)}</td>
                                <td className="pr-3">{e.max_scale_dev.toFixed(4)}</td>
                                <td className="pr-3 text-gray-400 font-mono truncate max-w-[180px]">{e.health_reason || '—'}</td>
                                <td className={e.used_fallback ? 'text-amber-400' : 'text-green-400'}>{e.used_fallback ? 'SCANS' : 'ASP'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )
                }
              </div>
            )}

            {activeTab === 'frames' && (
              <div className="space-y-4">
                <p className="text-xs text-gray-400">Frame selection funnel: original → smart_select (hold/phase-corr) → spatial_dedup → final.</p>
                {frameSelection.length === 0
                  ? <Empty msg="No frame selection data in benchmark output." />
                  : (
                    <>
                      <BarChart
                        labels={frameSelection.map(e => e.dataset)}
                        series={[
                          { label: 'Original', color: '#94a3b8', values: frameSelection.map(e => e.original_count) },
                          { label: 'After smart select', color: '#6366f1', values: frameSelection.map(e => e.smart_select_count) },
                          { label: 'After spatial dedup', color: '#22c55e', values: frameSelection.map(e => e.spatial_dedup_count) },
                          { label: 'Final (used)', color: '#fbbf24', values: frameSelection.map(e => e.final_count) },
                        ]}
                        yLabel="Frame count" xLabel="Dataset"
                        title="Frame Selection Funnel" height={300} />
                      <Legend items={[
                        { color: '#94a3b8', label: 'Original' },
                        { color: '#6366f1', label: 'After smart select' },
                        { color: '#22c55e', label: 'After spatial dedup' },
                        { color: '#fbbf24', label: 'Final' },
                      ]} />
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs text-gray-300">
                          <thead className="text-gray-400 border-b border-gray-700">
                            <tr>
                              {['Dataset', 'Original', 'Smart Sel', 'Spatial Dedup', 'Final', 'Drop %', 'Mode'].map(h => (
                                <th key={h} className="text-left py-1.5 pr-3">{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {frameSelection.map(e => (
                              <tr key={e.dataset} className="border-b border-gray-700/40 hover:bg-gray-700/20">
                                <td className="py-1.5 pr-3 font-mono">{e.dataset}</td>
                                <td className="pr-3">{e.original_count}</td>
                                <td className="pr-3">{e.smart_select_count} <span className="text-gray-500">(-{e.frames_dropped_smart})</span></td>
                                <td className="pr-3">{e.spatial_dedup_count} <span className="text-gray-500">(-{e.frames_dropped_dedup})</span></td>
                                <td className="pr-3 font-semibold">{e.final_count}</td>
                                <td className={`pr-3 ${e.drop_pct > 50 ? 'text-amber-400' : 'text-gray-300'}`}>{e.drop_pct.toFixed(1)}%</td>
                                <td className="pr-3 text-xs text-gray-400">{e.selection_mode}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )
                }
              </div>
            )}

            {activeTab === 'fallback' && (
              <div className="space-y-4">
                <p className="text-xs text-gray-400">Root-cause classification for datasets that fell back to SCANS stitcher.</p>
                {fallbackReasons.length === 0
                  ? <Empty msg="No datasets found." />
                  : (
                    <>
                      <BarChart
                        labels={fallbackReasons.map(e => e.reason_class)}
                        series={[
                          { label: 'Datasets', color: '#f87171', values: fallbackReasons.map(e => e.count) },
                        ]}
                        yLabel="Count" xLabel="Reason class"
                        title="Fallback Root-Cause Distribution" height={260} />
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs text-gray-300">
                          <thead className="text-gray-400 border-b border-gray-700">
                            <tr>
                              {['Reason Class', 'Count', '%', 'Datasets'].map(h => (
                                <th key={h} className="text-left py-1.5 pr-3">{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {fallbackReasons.map(e => (
                              <tr key={e.reason_class} className="border-b border-gray-700/40 hover:bg-gray-700/20">
                                <td className={`py-1.5 pr-3 font-mono font-semibold ${e.reason_class === 'none' ? 'text-green-400' : 'text-amber-400'}`}>{e.reason_class}</td>
                                <td className="pr-3">{e.count}</td>
                                <td className="pr-3">{e.pct.toFixed(1)}%</td>
                                <td className="pr-3 text-gray-400 text-xs">{e.datasets.join(', ').slice(0, 80)}{e.datasets.join(', ').length > 80 ? '…' : ''}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )
                }
              </div>
            )}

            {activeTab === 'gt' && (
              <div className="space-y-4">
                <p className="text-xs text-gray-400">Ground-truth comparison: SSIM and PSNR against reference frames (only available when GT provided).</p>
                {gtComparisons.length === 0
                  ? <Empty msg="No ground-truth data found. Provide GT images to the benchmark runner." />
                  : (
                    <>
                      <BarChart
                        labels={gtComparisons.map(e => e.dataset)}
                        series={[
                          { label: 'SSIM vs GT', color: '#6366f1', values: gtComparisons.map(e => e.ssim_vs_gt ?? 0) },
                          { label: 'Aligned SSIM vs GT', color: '#22c55e', values: gtComparisons.map(e => e.aligned_ssim_vs_gt ?? 0) },
                        ]}
                        yLabel="SSIM (0–1, higher=better)" xLabel="Dataset"
                        title="Structural Similarity vs Ground Truth" height={280} />
                      <BarChart
                        labels={gtComparisons.map(e => e.dataset)}
                        series={[
                          { label: 'PSNR vs GT (dB)', color: '#f59e0b', values: gtComparisons.map(e => e.psnr_vs_gt ?? 0) },
                        ]}
                        yLabel="PSNR (dB, higher=better)" xLabel="Dataset"
                        title="Peak Signal-to-Noise Ratio vs Ground Truth" height={240} />
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs text-gray-300">
                          <thead className="text-gray-400 border-b border-gray-700">
                            <tr>
                              {['Dataset', 'SSIM', 'Aligned SSIM', 'PSNR (dB)', 'Verdict', 'Mode'].map(h => (
                                <th key={h} className="text-left py-1.5 pr-3">{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {gtComparisons.map(e => (
                              <tr key={e.dataset} className="border-b border-gray-700/40 hover:bg-gray-700/20">
                                <td className="py-1.5 pr-3 font-mono">{e.dataset}</td>
                                <td className="pr-3">{e.ssim_vs_gt?.toFixed(4) ?? '—'}</td>
                                <td className="pr-3">{e.aligned_ssim_vs_gt?.toFixed(4) ?? '—'}</td>
                                <td className="pr-3">{e.psnr_vs_gt?.toFixed(1) ?? '—'}</td>
                                <td className={`pr-3 ${e.verdict === 'pass' ? 'text-green-400' : e.verdict ? 'text-amber-400' : 'text-gray-500'}`}>{e.verdict ?? '—'}</td>
                                <td className={e.used_fallback ? 'text-amber-400' : 'text-green-400'}>{e.used_fallback ? 'SCANS' : 'ASP'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )
                }
              </div>
            )}

            {activeTab === 'comparison' && datasets.length > 0 && (
              <div className="space-y-4">
                <BarChart
                  labels={datasets.map(d => d.name)}
                  series={[
                    { label: 'ASP Sharpness', color: '#4ade80', values: datasets.map(d => d.metrics_asp?.sharpness ?? 0) },
                    { label: 'Simple Sharpness', color: '#f87171', values: datasets.map(d => d.metrics_simple?.sharpness ?? 0) },
                  ]}
                  yLabel="Sharpness" xLabel="Dataset" title="Sharpness: ASP vs Simple" height={280} />
                <BarChart
                  labels={datasets.map(d => d.name)}
                  series={[
                    { label: 'ASP Coverage', color: '#4ade80', values: datasets.map(d => (d.metrics_asp?.coverage ?? 0) * 100) },
                    { label: 'Simple Coverage', color: '#f87171', values: datasets.map(d => (d.metrics_simple?.coverage ?? 0) * 100) },
                  ]}
                  yLabel="Coverage (%)" xLabel="Dataset" title="Coverage: ASP vs Simple" height={280} />
                <Legend items={[{ color: '#4ade80', label: 'ASP' }, { color: '#f87171', label: 'Simple Stitch' }]} />
              </div>
            )}

            {activeTab === 'heatmap' && heatRows.length > 0 && (
              <>
                <p className="text-xs text-gray-400 mb-2">All metrics mapped to [0,1] — brighter = better quality.</p>
                <Heatmap
                  cells={heatCells}
                  cols={heatCols}
                  rows={heatRows.map(rr => rr.dataset)}
                  title="Seam Quality Heatmap" />
                <Legend items={[
                  { color: '#440154', label: '0% (worst)' },
                  { color: '#31688e', label: '40%' },
                  { color: '#35b779', label: '70%' },
                  { color: '#fde725', label: '100% (best)' },
                ]} />
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ── System Comparison page ────────────────────────────────────────────────────

function SystemComparisonPage({ reports }: { reports: BenchmarkReport[] }) {
  if (reports.length < 2) return <Empty msg="Need at least 2 benchmark reports to compare systems." />;

  const rows = reports.map(r => ({
    kind: r.kind,
    file: r.file_name,
    suite: r.kind === 'General' ? r.suite_name : 'ASP',
    ts: r.system.timestamp.slice(0, 19),
    cpu: r.system.cpu.slice(0, 40),
    gpu: r.system.gpu?.slice(0, 25) ?? '—',
    ram: r.system.ram_gb ? `${r.system.ram_gb} GB` : '—',
    total_time: r.kind === 'General' ? r.summary.total_execution_time_sec.toFixed(2) : r.summary.total_time_sec.toFixed(2),
    peak_mem: r.kind === 'General' ? r.summary.max_peak_memory_mb.toFixed(0) : '—',
  }));

  return (
    <div className={CARD}>
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-gray-300">
          <thead className="text-gray-400 border-b border-gray-700">
            <tr>
              {['Suite', 'Timestamp', 'CPU', 'GPU', 'RAM', 'Total Time (s)', 'Peak Mem (MB)', 'File'].map(h => (
                <th key={h} className="text-left py-2 pr-4">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-b border-gray-700/40 hover:bg-gray-700/20">
                <td className="py-1.5 pr-4">{row.suite}</td>
                <td className="pr-4">{row.ts}</td>
                <td className="pr-4 max-w-40 truncate">{row.cpu}</td>
                <td className="pr-4">{row.gpu}</td>
                <td className="pr-4">{row.ram}</td>
                <td className="pr-4">{row.total_time}</td>
                <td className="pr-4">{row.peak_mem}</td>
                <td className="font-mono text-gray-500">{row.file.slice(0, 30)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Raw Data page ─────────────────────────────────────────────────────────────

function RawDataPage({ reports }: { reports: BenchmarkReport[] }) {
  const [selected, setSelected] = useState(0);
  const r = reports[selected];

  const download = useCallback(() => {
    if (!r) return;
    const blob = new Blob([JSON.stringify(r, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = r.file_name;
    a.click();
  }, [r]);

  return (
    <div className="space-y-3">
      <div className="flex gap-3 items-center">
        <select value={selected} onChange={e => setSelected(Number(e.target.value))}
          className="bg-gray-700 text-white text-sm rounded-lg border border-gray-600 px-3 py-1.5">
          {reports.map((r, i) => <option key={i} value={i}>{r.file_name}</option>)}
        </select>
        <button onClick={download} className="flex items-center gap-1.5 text-xs text-violet-400 hover:text-violet-300">
          <Download size={14} /> Download JSON
        </button>
      </div>
      {r && (
        <pre className="bg-gray-900 border border-gray-700 rounded-xl p-4 text-xs text-gray-300 overflow-auto max-h-[60vh]">
          {JSON.stringify(r, null, 2)}
        </pre>
      )}
    </div>
  );
}

// ── Main Dashboard ────────────────────────────────────────────────────────────

type Page = 'overview' | 'suite' | 'comparison' | 'trends' | 'asp' | 'system' | 'raw';

const PAGE_CONFIG: Array<{ id: Page; label: string; icon: React.ReactNode }> = [
  { id: 'overview', label: 'Overview', icon: <BarChart3 size={14} /> },
  { id: 'suite', label: 'Suite Analysis', icon: <Database size={14} /> },
  { id: 'comparison', label: 'Function Comparison', icon: <Activity size={14} /> },
  { id: 'trends', label: 'Trends', icon: <TrendingUp size={14} /> },
  { id: 'asp', label: 'ASP Pipeline', icon: <Cpu size={14} /> },
  { id: 'system', label: 'System Comparison', icon: <Zap size={14} /> },
  { id: 'raw', label: 'Raw Data', icon: <Eye size={14} /> },
];

export const BenchmarkDashboard: React.FC = () => {
  const [reports, setReports] = useState<BenchmarkReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState<Page>('overview');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await invoke<BenchmarkReport[]>('load_benchmark_reports', { limit: 200 });
      setReports(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="flex h-full bg-gray-900 text-gray-100 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-52 border-r border-gray-700 flex flex-col shrink-0">
        <div className="p-4 border-b border-gray-700">
          <div className="flex items-center gap-2 text-sm font-semibold text-gray-100">
            <BarChart3 size={16} className="text-violet-400" />
            Benchmark Dashboard
          </div>
          <div className="text-xs text-gray-500 mt-1">{reports.length} reports loaded</div>
        </div>
        <nav className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {PAGE_CONFIG.map(p => (
            <button key={p.id}
              onClick={() => setPage(p.id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 transition ${
                page === p.id
                  ? 'bg-violet-600/20 text-violet-300 border border-violet-600/30'
                  : 'text-gray-400 hover:text-white hover:bg-gray-700/50'
              }`}>
              {p.icon}
              {p.label}
            </button>
          ))}
        </nav>
        <div className="p-3 border-t border-gray-700">
          <button onClick={load} className="w-full flex items-center justify-center gap-1.5 text-xs text-gray-400 hover:text-white py-1.5 rounded-lg hover:bg-gray-700 transition">
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 size={24} className="animate-spin text-violet-400 mr-3" />
            <span className="text-gray-400">Loading benchmark reports…</span>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-full flex-col gap-3">
            <AlertCircle size={24} className="text-red-400" />
            <div className="text-red-300 text-sm max-w-md text-center">{error}</div>
            <button onClick={load} className="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm rounded-lg">Retry</button>
          </div>
        ) : (
          <>
            {page === 'overview' && <OverviewPage reports={reports} />}
            {page === 'suite' && <SuiteAnalysisPage reports={reports} />}
            {page === 'comparison' && <FunctionComparisonPage reports={reports} />}
            {page === 'trends' && <TrendsPage reports={reports} />}
            {page === 'asp' && <AspAnalysisPage reports={reports} />}
            {page === 'system' && <SystemComparisonPage reports={reports} />}
            {page === 'raw' && <RawDataPage reports={reports} />}
          </>
        )}
      </main>
    </div>
  );
};

export default BenchmarkDashboard;
