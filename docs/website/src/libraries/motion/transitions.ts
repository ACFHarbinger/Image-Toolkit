/** Motion variant seeds for docs-site demos. Prefer wiring `framer-motion`'s
 * Vue-compatible primitives (via `motion-v` or manual `AnimatePresence`
 * ports) when a hub panel needs a live enter/exit transition. */
export const fadeVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
  exit: { opacity: 0 },
};

export const slideUpVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -20 },
};

export const scaleInVariants = {
  hidden: { opacity: 0, scale: 0.96 },
  visible: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.96 },
};
