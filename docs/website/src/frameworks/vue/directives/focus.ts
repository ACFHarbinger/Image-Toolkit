import type { Directive } from "vue";

/** `v-focus="condition"` — focuses the element whenever `condition` becomes truthy. */
export const focus: Directive<HTMLElement, boolean> = {
  updated(el, binding) {
    if (binding.value && !binding.oldValue) el.focus();
  },
  mounted(el, binding) {
    if (binding.value) el.focus();
  },
};
