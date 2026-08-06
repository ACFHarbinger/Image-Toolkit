<script setup lang="ts">
import { ref, onMounted, nextTick } from "vue";
import { loadDoc } from "../composables/useDocs";
import { renderMarkdown } from "../composables/useMarkdown";
import { submoduleSites } from "../submodules";

interface FeatureCard {
  icon: string;
  title: string;
  desc: string;
  to: string;
}

const cards: FeatureCard[] = [
  {
    icon: "🚀",
    title: "Getting Started",
    desc: "Install the toolkit, set up the environment, and understand the module layout.",
    to: "/readme",
  },
  {
    icon: "🧭",
    title: "Tutorials",
    desc: "Walkthroughs for every GUI tab category, from library management to deep learning.",
    to: "/tutorials/index",
  },
  {
    icon: "📖",
    title: "Reference",
    desc: "REST, Python, Rust, TypeScript, and Kotlin API documentation, generated from source.",
    to: "/api/rest-api",
  },
  {
    icon: "🗺️",
    title: "Roadmaps",
    desc: "What's shipped, what's in progress, and where each subsystem is headed next.",
    to: "/roadmaps/ROADMAP",
  },
  {
    icon: "🔬",
    title: "Research",
    desc: "The papers, algorithms, and design notes behind the toolkit's core features.",
    to: "/research/analytics",
  },
  {
    icon: "🧩",
    title: "Submodules",
    desc: "Anime-Stitch-Pipeline, Cel-Shaded-Generator, and Recommendation-Engine docs.",
    to: submoduleSites.length ? "/submodules/" + submoduleSites[0].slug : "/CHANGELOG",
  },
];

const state = ref<"loading" | "ok" | "notfound">("loading");
const html = ref("");

async function renderMermaid() {
  const nodes = document.querySelectorAll<HTMLElement>(".home-readme .mermaid");
  if (!nodes.length) return;
  const mermaid = (await import("mermaid")).default;
  mermaid.initialize({
    startOnLoad: false,
    theme: document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "default",
    securityLevel: "loose",
  });
  try {
    await mermaid.run({ nodes: Array.from(nodes) });
  } catch (e) {
    console.warn("mermaid render failed", e);
  }
}

async function load() {
  const raw = await loadDoc("index.md");
  if (raw === null) {
    state.value = "notfound";
    return;
  }
  html.value = renderMarkdown(raw);
  state.value = "ok";
  await nextTick();
  renderMermaid();
}

onMounted(load);
</script>

<template>
  <div class="home">
    <section class="hero-section">
      <div class="hero-overlay" />
      <div class="hero-content">
        <span class="badge">Documentation</span>
        <h1>Image-Toolkit</h1>
        <p class="hero-desc">
          An image database and editing toolkit with a high-performance C++/Rust backend, a Tauri
          cross-platform frontend, and machine-learning pipelines for stitching, colorization, and
          recommendation. Everything you need to build, extend, or just use it, in one place.
        </p>
        <div class="hero-actions">
          <router-link to="/readme" class="btn btn-primary">Quick Start</router-link>
          <router-link to="/ARCHITECTURE" class="btn btn-secondary">Read the Architecture</router-link>
          <router-link to="/api/rest-api" class="btn btn-secondary">Browse the API</router-link>
        </div>
      </div>
    </section>

    <section class="feature-grid-section">
      <div class="feature-grid">
        <router-link v-for="c in cards" :key="c.title" :to="c.to" class="feature-card panel-glass">
          <span class="feature-icon">{{ c.icon }}</span>
          <h3>{{ c.title }}</h3>
          <p>{{ c.desc }}</p>
        </router-link>
      </div>
    </section>

    <section class="home-readme">
      <div v-if="state === 'loading'" class="doc-loading">Loading…</div>
      <div v-else-if="state === 'ok'" class="markdown-body" v-html="html" />
    </section>
  </div>
</template>

<style scoped>
.hero-section {
  position: relative;
  padding: 4.5rem 2rem 3rem;
  overflow: hidden;
}
.hero-overlay {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 20% 15%, color-mix(in srgb, var(--accent) 14%, transparent), transparent 60%),
    radial-gradient(circle at 85% 30%, color-mix(in srgb, var(--accent-2) 12%, transparent), transparent 55%);
  pointer-events: none;
}
.hero-content {
  position: relative;
  z-index: 1;
  max-width: 720px;
  margin: 0 auto;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.hero-content h1 {
  font-family: var(--font-display);
  font-size: 3rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  margin: 1.25rem 0 1rem;
}
.hero-desc {
  font-size: 1.05rem;
  color: var(--text-muted);
  line-height: 1.65;
  margin: 0 0 2rem;
}
.hero-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.85rem;
}

.feature-grid-section {
  max-width: 1100px;
  margin: 0 auto;
  padding: 0 2rem 3rem;
}
.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1.25rem;
}
.feature-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 1.5rem;
  color: var(--text);
}
.feature-icon {
  font-size: 1.6rem;
  margin-bottom: 0.75rem;
}
.feature-card h3 {
  margin: 0 0 0.5rem;
  font-size: 1.05rem;
  font-weight: 700;
}
.feature-card p {
  margin: 0;
  font-size: 0.875rem;
  color: var(--text-muted);
  line-height: 1.5;
}

.home-readme {
  max-width: 900px;
  margin: 0 auto;
  padding: 1rem 2rem 6rem;
  border-top: 1px solid var(--border);
  padding-top: 3rem;
}
.doc-loading {
  text-align: center;
  color: var(--text-muted);
  padding: 3rem 0;
}

@media (max-width: 640px) {
  .hero-content h1 {
    font-size: 2.25rem;
  }
}
</style>
