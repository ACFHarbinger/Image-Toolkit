<script setup lang="ts">
/**
 * Benchmark + human-coherence ratings dashboard (scaffold).
 *
 * Loads optional JSON from public/data/ (copy or symlink after rating sessions):
 *   - public/data/asp_evaluations.json  (or latest asp_evaluations_*.json renamed)
 *   - public/data/benchmark_results.json
 *
 * Full interactive charts / 2D–3D islands land in the React parity migration.
 * This view ships the schema, summary stats, and export instructions so Harbinger
 * can start rating while the site migration proceeds.
 */
import { computed, onMounted, ref } from "vue";

interface EvaluationEntry {
  asp?: number;
  simple?: number;
  preference?: string;
  confidence?: number;
  defects?: string[];
  reviewed?: boolean;
  notes?: string;
}

type EvaluationsFile = Record<string, EvaluationEntry>;

const loading = ref(true);
const error = ref<string | null>(null);
const evaluations = ref<EvaluationsFile>({});
const sourceLabel = ref<string>("(none loaded)");

const entries = computed(() => Object.entries(evaluations.value));
const reviewed = computed(() => entries.value.filter(([, e]) => e.reviewed || e.asp != null));
const scoreHistAsp = computed(() => histogram(reviewed.value.map(([, e]) => e.asp)));
const scoreHistSimple = computed(() => histogram(reviewed.value.map(([, e]) => e.simple)));
const prefCounts = computed(() => {
  const c: Record<string, number> = {};
  for (const [, e] of reviewed.value) {
    const p = e.preference || "unset";
    c[p] = (c[p] || 0) + 1;
  }
  return c;
});
const meanAsp = computed(() => mean(reviewed.value.map(([, e]) => e.asp)));
const meanSimple = computed(() => mean(reviewed.value.map(([, e]) => e.simple)));

function histogram(scores: (number | undefined)[]): Record<number, number> {
  const h: Record<number, number> = { 0: 0, 1: 0, 2: 0, 3: 0, 4: 0 };
  for (const s of scores) {
    if (s == null || Number.isNaN(s)) continue;
    const k = Math.max(0, Math.min(4, Math.round(s)));
    h[k] = (h[k] || 0) + 1;
  }
  return h;
}

function mean(scores: (number | undefined)[]): string {
  const v = scores.filter((s): s is number => typeof s === "number");
  if (!v.length) return "—";
  return (v.reduce((a, b) => a + b, 0) / v.length).toFixed(2);
}

async function tryLoad(url: string): Promise<EvaluationsFile | null> {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    return (await res.json()) as EvaluationsFile;
  } catch {
    return null;
  }
}

onMounted(async () => {
  loading.value = true;
  error.value = null;
  // Prefer a stable name; fall back to example empty state.
  const candidates = [
    "/data/asp_evaluations.json",
    "/data/benchmarks/asp_evaluations.json",
  ];
  let loaded: EvaluationsFile | null = null;
  for (const url of candidates) {
    loaded = await tryLoad(url);
    if (loaded && Object.keys(loaded).length) {
      sourceLabel.value = url;
      break;
    }
  }
  evaluations.value = loaded || {};
  if (!Object.keys(evaluations.value).length) {
    error.value =
      "No evaluation JSON found under public/data/. Run just asp-benchmark-assess, then copy the latest data/benchmarks/asp_evaluations_*.json to docs/website/public/data/asp_evaluations.json";
  }
  loading.value = false;
});
</script>

<template>
  <div class="ratings-dash">
    <header class="dash-hero">
      <p class="eyebrow">Analysis · ASP quality</p>
      <h1>Benchmark ratings dashboard</h1>
      <p class="lede">
        Human structural-coherence scores (0–4) and comparator preferences over the ASP corpus.
        Automated metrics alone do not measure torn anatomy or misordered content — this board
        tracks the human rating pass and (soon) time-series benchmark JSON.
      </p>
      <div class="actions">
        <router-link class="btn" to="/">← Hub</router-link>
        <code class="cmd">just asp-benchmark-assess</code>
      </div>
    </header>

    <section v-if="loading" class="panel">Loading…</section>
    <section v-else-if="error" class="panel warn">
      <h2>Waiting for rating data</h2>
      <p>{{ error }}</p>
      <ol>
        <li>Produce stitch outputs under <code>dump/</code> (or your data dir).</li>
        <li>Run <code>just asp-benchmark-assess</code> and rate tests.</li>
        <li>
          Copy
          <code>data/benchmarks/asp_evaluations_YYYYMMDD.json</code>
          →
          <code>docs/website/public/data/asp_evaluations.json</code>
        </li>
        <li>Reload this page.</li>
      </ol>
    </section>

    <template v-else>
      <section class="stats">
        <div class="stat">
          <span class="label">Reviewed</span>
          <span class="value">{{ reviewed.length }} / {{ entries.length || reviewed.length }}</span>
        </div>
        <div class="stat">
          <span class="label">Mean ASP</span>
          <span class="value">{{ meanAsp }}</span>
        </div>
        <div class="stat">
          <span class="label">Mean Simple</span>
          <span class="value">{{ meanSimple }}</span>
        </div>
        <div class="stat">
          <span class="label">Source</span>
          <span class="value small">{{ sourceLabel }}</span>
        </div>
      </section>

      <section class="panel">
        <h2>ASP score histogram</h2>
        <div class="bars">
          <div v-for="s in [0, 1, 2, 3, 4]" :key="'a' + s" class="bar-row">
            <span class="bar-label">{{ s }}</span>
            <div class="bar-track">
              <div
                class="bar-fill asp"
                :style="{ width: (reviewed.length ? (100 * (scoreHistAsp[s] || 0)) / reviewed.length : 0) + '%' }"
              />
            </div>
            <span class="bar-count">{{ scoreHistAsp[s] || 0 }}</span>
          </div>
        </div>
      </section>

      <section class="panel">
        <h2>Simple (SCANS) score histogram</h2>
        <div class="bars">
          <div v-for="s in [0, 1, 2, 3, 4]" :key="'s' + s" class="bar-row">
            <span class="bar-label">{{ s }}</span>
            <div class="bar-track">
              <div
                class="bar-fill simple"
                :style="{ width: (reviewed.length ? (100 * (scoreHistSimple[s] || 0)) / reviewed.length : 0) + '%' }"
              />
            </div>
            <span class="bar-count">{{ scoreHistSimple[s] || 0 }}</span>
          </div>
        </div>
      </section>

      <section class="panel">
        <h2>Pairwise preference</h2>
        <ul class="pref-list">
          <li v-for="(n, k) in prefCounts" :key="k">
            <strong>{{ k }}</strong>: {{ n }}
          </li>
        </ul>
      </section>

      <section class="panel">
        <h2>Per-test table</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Test</th>
                <th>ASP</th>
                <th>Simple</th>
                <th>Preference</th>
                <th>Confidence</th>
                <th>Defects</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="[id, e] in reviewed" :key="id">
                <td><code>{{ id }}</code></td>
                <td>{{ e.asp ?? "—" }}</td>
                <td>{{ e.simple ?? "—" }}</td>
                <td>{{ e.preference ?? "—" }}</td>
                <td>{{ e.confidence ?? "—" }}</td>
                <td>{{ (e.defects || []).join(", ") || "—" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <footer class="dash-foot">
      <p>
        Next: multi-file time series (all <code>asp_evaluations_*.json</code>), metric-vs-human disagreement
        plots, and React/2D–3D islands for PMF-level visual parity. Coord:
        <code>.agent/cache/AGENT_BUS.md</code>
      </p>
    </footer>
  </div>
</template>

<style scoped>
.ratings-dash {
  max-width: 1100px;
  margin: 0 auto;
  padding: 2rem 1.25rem 4rem;
  color: var(--text, #e8eef7);
}
.dash-hero {
  margin-bottom: 2rem;
}
.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.75rem;
  opacity: 0.7;
}
.lede {
  max-width: 62ch;
  line-height: 1.55;
  opacity: 0.9;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
  margin-top: 1rem;
}
.btn {
  display: inline-block;
  padding: 0.45rem 0.9rem;
  border-radius: 0.5rem;
  background: rgba(99, 140, 255, 0.2);
  border: 1px solid rgba(99, 140, 255, 0.45);
  color: inherit;
  text-decoration: none;
}
.cmd {
  font-size: 0.85rem;
  padding: 0.35rem 0.6rem;
  border-radius: 0.35rem;
  background: rgba(0, 0, 0, 0.35);
}
.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}
.stat {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 0.75rem;
  padding: 0.9rem 1rem;
}
.stat .label {
  display: block;
  font-size: 0.75rem;
  opacity: 0.65;
  margin-bottom: 0.35rem;
}
.stat .value {
  font-size: 1.4rem;
  font-weight: 600;
}
.stat .value.small {
  font-size: 0.8rem;
  word-break: break-all;
}
.panel {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 0.85rem;
  padding: 1.1rem 1.2rem;
  margin-bottom: 1rem;
}
.panel.warn {
  border-color: rgba(255, 180, 80, 0.45);
}
.bars {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.bar-row {
  display: grid;
  grid-template-columns: 1.5rem 1fr 2rem;
  gap: 0.5rem;
  align-items: center;
}
.bar-track {
  height: 0.65rem;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 999px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  border-radius: 999px;
}
.bar-fill.asp {
  background: linear-gradient(90deg, #5b8cff, #8b5cf6);
}
.bar-fill.simple {
  background: linear-gradient(90deg, #34d399, #2dd4bf);
}
.table-wrap {
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}
th,
td {
  text-align: left;
  padding: 0.45rem 0.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.dash-foot {
  margin-top: 2rem;
  opacity: 0.7;
  font-size: 0.9rem;
}
.pref-list {
  margin: 0;
  padding-left: 1.2rem;
}
</style>
