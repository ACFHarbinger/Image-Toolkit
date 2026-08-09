<script setup lang="ts">
import { ref, computed } from "vue";
import { moduleCards } from "../../../../constants/modules";
import type { ModuleCard } from "../../../../interfaces/types";

const layers: Array<{ id: ModuleCard["layer"] | "all"; label: string }> = [
  { id: "all", label: "All layers" },
  { id: "engine", label: "Engine" },
  { id: "interface", label: "Interface" },
  { id: "data", label: "Data" },
  { id: "security", label: "Security" },
];

const activeLayer = ref<(typeof layers)[number]["id"]>("all");

const filtered = computed(() =>
  activeLayer.value === "all" ? moduleCards : moduleCards.filter((m) => m.layer === activeLayer.value)
);
</script>

<template>
  <div class="modules-panel">
    <p class="lede">
      Every module in the polyglot module dependency graph — from <code>.agent/AGENTS.md</code> §4 and
      <code>docs/ARCHITECTURE.md</code> — click through to its reference docs.
    </p>

    <div class="layer-filter" role="group" aria-label="Filter modules by layer">
      <button
        v-for="l in layers"
        :key="l.id"
        class="layer-btn"
        :class="{ active: activeLayer === l.id }"
        @click="activeLayer = l.id"
      >
        {{ l.label }}
      </button>
    </div>

    <div class="module-grid">
      <router-link v-for="m in filtered" :key="m.slug" :to="m.path" class="module-card panel">
        <div class="module-card-head">
          <span class="module-title">{{ m.title }}</span>
          <span class="module-layer" :data-layer="m.layer">{{ m.layer }}</span>
        </div>
        <p class="module-tagline">{{ m.tagline }}</p>
        <p class="module-desc">{{ m.description }}</p>
        <div class="module-stack">
          <span v-for="s in m.stack" :key="s" class="stack-chip">{{ s }}</span>
        </div>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.lede {
  max-width: 46rem;
  color: var(--text-muted);
  margin: 0 0 1.25rem;
}
.layer-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 1.5rem;
}
.layer-btn {
  padding: 0.4rem 0.9rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
  border: 1px solid var(--border);
  color: var(--text-muted);
}
.layer-btn:hover {
  color: var(--text);
  border-color: var(--accent);
}
.layer-btn.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}
.module-card {
  display: block;
  padding: 1.1rem 1.2rem;
  transition: border-color 0.15s ease, transform 0.15s ease;
}
.module-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
}
.module-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}
.module-title {
  font-weight: 700;
  font-size: 0.98rem;
}
.module-layer {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 700;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background: var(--surface-hover);
  color: var(--text-muted);
}
.module-layer[data-layer="engine"] {
  color: var(--accent);
}
.module-layer[data-layer="security"] {
  color: #e11d48;
}
.module-tagline {
  margin: 0 0 0.5rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--accent);
}
.module-desc {
  margin: 0 0 0.75rem;
  font-size: 0.85rem;
  line-height: 1.55;
  color: var(--text-muted);
}
.module-stack {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}
.stack-chip {
  font-size: 0.7rem;
  padding: 0.15rem 0.5rem;
  border-radius: 6px;
  background: var(--surface-hover);
  color: var(--text-muted);
}
</style>
