<script setup lang="ts">
import { roadmapCards } from "../../../../constants/roadmap";
import { benchmarkSuites } from "../../../../constants/benchmarks";
</script>

<template>
  <div class="roadmap-panel">
    <section>
      <h3 class="subhead">Feature roadmaps</h3>
      <div class="roadmap-grid">
        <router-link v-for="r in roadmapCards" :key="r.slug" :to="r.path" class="roadmap-card panel">
          <h4>{{ r.title }}</h4>
          <p>{{ r.summary }}</p>
        </router-link>
      </div>
    </section>

    <section>
      <h3 class="subhead">Benchmark suite index</h3>
      <p class="lede">
        From <router-link to="/BENCHMARKS">docs/BENCHMARKS.md</router-link> — measures memory usage and compute
        time across the Python backend, C++ base layer, and the TypeScript analytics math backbone this site's
        API reference (<router-link to="/api/typescript/readme">TypeScript API</router-link>) documents.
      </p>
      <div class="table-wrap panel">
        <table>
          <thead>
            <tr>
              <th>Suite</th>
              <th>Runner</th>
              <th>Location</th>
              <th>Output</th>
              <th>CI job</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="b in benchmarkSuites" :key="b.suite">
              <td class="suite-name">{{ b.suite }}</td>
              <td><code>{{ b.runner }}</code></td>
              <td><code>{{ b.location }}</code></td>
              <td>{{ b.output }}</td>
              <td>{{ b.ciJob }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.roadmap-panel {
  display: flex;
  flex-direction: column;
  gap: 2.25rem;
}
.subhead {
  font-size: 1.05rem;
  margin: 0 0 0.9rem;
}
.lede {
  color: var(--text-muted);
  font-size: 0.88rem;
  max-width: 50rem;
  margin: 0 0 1rem;
}
.roadmap-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 0.9rem;
}
.roadmap-card {
  display: block;
  padding: 0.9rem 1.1rem;
}
.roadmap-card:hover {
  border-color: var(--accent);
}
.roadmap-card h4 {
  margin: 0 0 0.35rem;
  font-size: 0.9rem;
}
.roadmap-card p {
  margin: 0;
  font-size: 0.8rem;
  color: var(--text-muted);
  line-height: 1.5;
}
.table-wrap {
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}
th,
td {
  padding: 0.6rem 0.9rem;
  text-align: left;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
th {
  color: var(--text-muted);
  font-weight: 600;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.suite-name {
  font-weight: 600;
}
tr:last-child td {
  border-bottom: none;
}
</style>
