<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from "vue";
import { useTheme } from "../../../composables/useTheme";
import { logIslandMount, logIslandUnmount } from "../../shared/utils";

const props = withDefaults(
  defineProps<{
    /** iframe height */
    height?: string;
    /** Optional title override for accessibility */
    title?: string;
  }>(),
  {
    height: "420px",
    title: "Astro vector flow field island",
  }
);

const loaded = ref(false);
const failed = ref(false);
const inView = ref(false);
const frameEl = ref<HTMLIFrameElement | null>(null);
const { theme } = useTheme();

// public/ assets need BASE_URL when deployed under a GitHub Pages subpath.
const islandSrc = computed(() => `${import.meta.env.BASE_URL}astro-island/index.html`);

function postTheme() {
  frameEl.value?.contentWindow?.postMessage({ type: "image-toolkit-theme", theme: theme.value }, "*");
}

function onLoad() {
  loaded.value = true;
  logIslandMount("Astro", "vector-flow-field");
  postTheme();
}

function onError() {
  failed.value = true;
}

function onEnterViewport() {
  inView.value = true;
}

watch(theme, postTheme);
onUnmounted(() => logIslandUnmount("Astro", "vector-flow-field"));
</script>

<template>
  <section class="astro-island-wrap" :data-in-view="inView ? 'true' : 'false'" v-intersect="{ handler: onEnterViewport, once: true, threshold: 0.2 }">
    <div class="frame-shell" :style="{ minHeight: height }">
      <p v-if="failed" class="fallback" role="alert">
        Astro island failed to load. Rebuild with <code>npm run build:astro</code> so
        <code>public/astro-island/</code> is present.
      </p>
      <iframe
        v-show="!failed"
        ref="frameEl"
        class="island-frame"
        :src="islandSrc"
        :title="props.title"
        :style="{ height }"
        loading="lazy"
        referrerpolicy="no-referrer"
        @load="onLoad"
        @error="onError"
      />
      <p v-if="!loaded && !failed" class="loading">Loading Astro island…</p>
    </div>
  </section>
</template>

<style scoped>
.astro-island-wrap {
  margin: 0.5rem 0;
}
.frame-shell {
  position: relative;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border);
  background: var(--surface);
}
.island-frame {
  width: 100%;
  border: 0;
  display: block;
  background: transparent;
}
.loading,
.fallback {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  margin: 0;
  padding: 1rem;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9rem;
}
.fallback code {
  font-size: 0.85em;
}
</style>
