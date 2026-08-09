<script setup lang="ts">
import { ref } from "vue";
import { submoduleSites } from "../../../../constants/submodules";

const loaded = ref<Record<string, boolean>>({});
const revealed = ref<Record<string, boolean>>({});

function reveal(slug: string) {
  revealed.value[slug] = true;
}
</script>

<template>
  <div class="ecosystem-panel">
    <p class="lede">
      Sibling repositories under <code>submodules/</code> — each ships its own docs/website/ built from this same
      architecture and deployed to its own GitHub Pages. Embedded live here so they're reachable without leaving
      this site's chrome.
    </p>

    <div class="submodule-grid">
      <div
        v-for="s in submoduleSites"
        :key="s.slug"
        class="submodule-card panel"
        v-intersect="{ handler: () => reveal(s.slug), once: true, threshold: 0.15 }"
      >
        <header class="submodule-head">
          <div>
            <h3>{{ s.title }}</h3>
            <p>{{ s.description }}</p>
          </div>
          <a :href="s.repo" target="_blank" rel="noopener noreferrer" class="repo-link" aria-label="Repository">
            ↗
          </a>
        </header>
        <div class="frame-shell">
          <iframe
            v-if="revealed[s.slug]"
            class="submodule-frame"
            :src="s.url"
            :title="`${s.title} documentation`"
            loading="lazy"
            referrerpolicy="no-referrer"
            @load="loaded[s.slug] = true"
          />
          <p v-if="revealed[s.slug] && !loaded[s.slug]" class="loading">Loading {{ s.title }}…</p>
          <p v-else-if="!revealed[s.slug]" class="loading">Scroll into view to load…</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.lede {
  max-width: 46rem;
  color: var(--text-muted);
  margin: 0 0 1.5rem;
}
.submodule-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1.25rem;
}
.submodule-card {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.submodule-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
}
.submodule-head h3 {
  margin: 0 0 0.2rem;
  font-size: 0.98rem;
}
.submodule-head p {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-muted);
}
.repo-link {
  flex: none;
  color: var(--text-muted);
  font-size: 1rem;
}
.repo-link:hover {
  color: var(--accent);
}
.frame-shell {
  position: relative;
  min-height: 320px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border);
  background: var(--surface-hover);
}
.submodule-frame {
  width: 100%;
  height: 320px;
  border: 0;
  display: block;
}
.loading {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  margin: 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}
</style>
