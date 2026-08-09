import type { Directive } from "vue";

interface IntersectBinding {
  handler: () => void;
  once?: boolean;
  threshold?: number;
}

interface IntersectEl extends HTMLElement {
  __intersectObserver__?: IntersectionObserver;
}

/** `v-intersect="{ handler, once, threshold }"` — runs `handler` when the element enters the viewport. */
export const intersect: Directive<IntersectEl, IntersectBinding> = {
  mounted(el, binding) {
    const { handler, once = false, threshold = 0.1 } = binding.value;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            handler();
            if (once) observer.disconnect();
          }
        }
      },
      { threshold }
    );
    observer.observe(el);
    el.__intersectObserver__ = observer;
  },
  unmounted(el) {
    el.__intersectObserver__?.disconnect();
  },
};
