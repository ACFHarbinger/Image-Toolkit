<script setup lang="ts">
import ModulesPanel from "../components/hub/ModulesPanel.vue";
import EcosystemPanel from "../components/hub/EcosystemPanel.vue";
import RoadmapPanel from "../components/hub/RoadmapPanel.vue";
import VectorFlowFieldWrapper from "../../astro/components/VectorFlowFieldWrapper.vue";
import ComponentGalleryWrapper from "../components/hub/ComponentGalleryWrapper.vue";
import AnnConvergenceWrapper from "../../aurelia/AnnConvergenceWrapper.vue";
import { useAppStore } from "../../../libraries/vuex/store/hooks";

interface Tab {
  id: string;
  label: string;
  icon: string;
}

const tabs: Tab[] = [
  { id: "modules", label: "Module Explorer", icon: "🧩" },
  { id: "ecosystem", label: "Ecosystem", icon: "🌐" },
  { id: "roadmap", label: "Roadmap & Benchmarks", icon: "🗺️" },
  { id: "islands", label: "Framework Islands", icon: "🏝️" },
];

// Persisted in Vuex (localStorage-backed) rather than a local ref, so the
// hub remembers which tab you were on across a reload.
const { activeHubTab: activeTab, selectHubTab: setActiveTab } = useAppStore();
</script>

<template>
  <div class="hub">
    <section class="hub-hero">
      <h1>Image-Toolkit</h1>
      <p>
        An integrated image database and editing framework — high-performance computer vision, semantic vector
        search, web automation, and a cross-platform GUI, spanning Python, C++, Kotlin, Swift, and TypeScript.
      </p>
      <div class="hero-actions">
        <router-link to="/docs" class="btn btn-primary">Read the docs</router-link>
        <router-link to="/dashboard/ratings" class="btn btn-secondary">Ratings dashboard</router-link>
        <a class="btn btn-secondary" href="https://github.com/ACFHarbinger/Image-Toolkit" target="_blank" rel="noopener noreferrer">
          View on GitHub ↗
        </a>
      </div>
    </section>

    <section class="hub-tabs-section">
      <div class="tabs-header" role="tablist" aria-label="Engineering hub sections">
        <button
          v-for="t in tabs"
          :key="t.id"
          class="tab-btn"
          role="tab"
          :aria-selected="activeTab === t.id"
          :class="{ active: activeTab === t.id }"
          @click="setActiveTab(t.id)"
        >
          <span aria-hidden="true">{{ t.icon }}</span> {{ t.label }}
        </button>
      </div>

      <ModulesPanel v-if="activeTab === 'modules'" />
      <EcosystemPanel v-else-if="activeTab === 'ecosystem'" />
      <RoadmapPanel v-else-if="activeTab === 'roadmap'" />
      <div v-else-if="activeTab === 'islands'" class="islands-panel">
        <p class="lede">
          This site's own chrome is Vue 3, but it embeds three more frameworks as isolated "islands" — each one
          mounting real, working functionality rather than a placeholder.
        </p>
        <div class="island-frame">
          <div class="island-label">Astro · static-rendered, iframe-embedded</div>
          <VectorFlowFieldWrapper />
        </div>
        <ComponentGalleryWrapper />
        <div class="island-frame">
          <div class="island-label">Aurelia 2 · mounted in-place via app.start()</div>
          <AnnConvergenceWrapper />
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.hero-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: center;
  margin-top: 1.75rem;
  flex-wrap: wrap;
}
.islands-panel {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}
.lede {
  max-width: 46rem;
  color: var(--text-muted);
  margin: 0 0 0.5rem;
}
</style>
