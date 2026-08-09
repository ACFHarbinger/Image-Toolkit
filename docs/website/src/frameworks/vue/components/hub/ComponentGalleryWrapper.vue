<script setup lang="ts">
// Mounts the real React island (ComponentGallery.tsx, which imports
// Image-Toolkit's actual frontend/src/components/common/* — no port, no
// copy) into a Vue-owned DOM node via ReactDOM.createRoot. Vite's @vitejs/
// plugin-react (scoped to frameworks/react/**/*.tsx in vite.config.ts) is
// what makes the .tsx import below compile at all inside a Vue project.
import { onMounted, onUnmounted, ref } from "vue";
import type { Root } from "react-dom/client";

const hostEl = ref<HTMLDivElement | null>(null);
let root: Root | null = null;

onMounted(async () => {
  if (!hostEl.value) return;
  const [{ createRoot }, React, { default: ComponentGallery }] = await Promise.all([
    import("react-dom/client"),
    import("react"),
    import("../../../react/ComponentGallery"),
  ]);
  root = createRoot(hostEl.value);
  root.render(React.createElement(ComponentGallery));
});

onUnmounted(() => {
  // Unmount outside React's own commit phase so the teardown doesn't race
  // Vue's own DOM removal of hostEl.
  const r = root;
  root = null;
  if (r) queueMicrotask(() => r.unmount());
});
</script>

<template>
  <section class="react-island-wrap">
    <p class="island-label">Framework island · React — live frontend/src/components/common/*</p>
    <div ref="hostEl" class="react-host" />
  </section>
</template>

<style scoped>
.react-island-wrap {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1rem;
  background: var(--surface);
}
.island-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin: 0 0 0.75rem;
}
.react-host :deep(.component-gallery) {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.react-host :deep(.gallery-btn) {
  padding: 0.5rem 0.9rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface-hover);
  color: var(--text);
  font-size: 0.85rem;
  font-weight: 600;
}
.react-host :deep(.gallery-btn:hover) {
  border-color: var(--accent);
  color: var(--accent);
}
</style>
