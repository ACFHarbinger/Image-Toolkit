import type { Directive } from "vue";

interface ClickOutsideEl extends HTMLElement {
  __clickOutsideHandler__?: (e: MouseEvent) => void;
}

/** `v-click-outside="handler"` — invokes `handler` on any click outside the bound element. */
export const clickOutside: Directive<ClickOutsideEl, () => void> = {
  mounted(el, binding) {
    el.__clickOutsideHandler__ = (e: MouseEvent) => {
      if (!(e.target instanceof Node) || el === e.target || el.contains(e.target)) return;
      binding.value?.();
    };
    document.addEventListener("click", el.__clickOutsideHandler__, true);
  },
  unmounted(el) {
    if (el.__clickOutsideHandler__) {
      document.removeEventListener("click", el.__clickOutsideHandler__, true);
      delete el.__clickOutsideHandler__;
    }
  },
};
