<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import type { AureliaMountHandle } from "./mount";

const hostEl = ref<HTMLDivElement | null>(null);
let handle: AureliaMountHandle | null = null;

onMounted(async () => {
  if (!hostEl.value) return;
  const { mountAnnConvergence } = await import("./mount");
  handle = mountAnnConvergence(hostEl.value);
});

onUnmounted(() => {
  void handle?.stop();
  handle = null;
});
</script>

<template>
  <div ref="hostEl" class="aurelia-host" />
</template>

<style scoped>
.aurelia-host :deep(.ann-root) {
  font-family: inherit;
  color: var(--text);
}
.aurelia-host :deep(.kicker) {
  margin: 0 0 0.2rem;
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}
.aurelia-host :deep(h2) {
  margin: 0 0 0.35rem;
  font-size: 1.05rem;
}
.aurelia-host :deep(.subtitle) {
  margin: 0 0 0.75rem;
  font-size: 0.82rem;
  color: var(--text-muted);
}
.aurelia-host :deep(.controls) {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}
.aurelia-host :deep(select),
.aurelia-host :deep(button) {
  padding: 0.4rem 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface-hover);
  color: var(--text);
  font-size: 0.8rem;
  font-weight: 600;
}
.aurelia-host :deep(button:hover) {
  border-color: var(--accent);
  color: var(--accent);
}
.aurelia-host :deep(.step-label) {
  font-size: 0.75rem;
  color: var(--text-muted);
}
.aurelia-host :deep(svg) {
  width: 100%;
  height: auto;
  aspect-ratio: 1;
  max-height: 320px;
  display: block;
}
</style>
