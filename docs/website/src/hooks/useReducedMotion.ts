import { onBeforeUnmount, onMounted, ref } from "vue";

export function useReducedMotion() {
  const prefersReduced = ref(false);
  let mql: MediaQueryList | null = null;
  const update = () => {
    prefersReduced.value = mql?.matches ?? false;
  };

  onMounted(() => {
    mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    update();
    mql.addEventListener("change", update);
  });
  onBeforeUnmount(() => mql?.removeEventListener("change", update));

  return prefersReduced;
}
