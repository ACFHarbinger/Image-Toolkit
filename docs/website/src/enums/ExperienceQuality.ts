// Parametrizes how much motion/simulation work the hub panels do — read by
// src/configs/hubExperience.ts and by the Aurelia/Astro islands, honoring
// prefers-reduced-motion (see src/hooks/useReducedMotion.ts) and coarse
// device-memory hints so low-power devices don't inherit desktop defaults.
export enum ExperienceQuality {
  Minimal = "minimal",
  Balanced = "balanced",
  Full = "full",
}

export function experienceQualityFromEnvironment(): ExperienceQuality {
  if (typeof window === "undefined") return ExperienceQuality.Balanced;
  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  if (reducedMotion) return ExperienceQuality.Minimal;
  const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory;
  if (typeof memory === "number" && memory <= 4) return ExperienceQuality.Balanced;
  return ExperienceQuality.Full;
}
