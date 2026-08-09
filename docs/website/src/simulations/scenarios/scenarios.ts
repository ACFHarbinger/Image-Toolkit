import type { ConvergenceScenario } from "../repository/types";

export const scenarios: ConvergenceScenario[] = [
  {
    id: "gallery-small",
    title: "Small gallery (200 images)",
    description: "A small personal library — converges in a handful of steps.",
    seed: 7,
    pointCount: 60,
    clusterCount: 4,
    maxSteps: 24,
  },
  {
    id: "gallery-large",
    title: "Large gallery (50k+ images)",
    description: "A large crawled corpus (danbooru/gelbooru/sankaku) — more clusters, slower settling.",
    seed: 42,
    pointCount: 160,
    clusterCount: 8,
    maxSteps: 40,
  },
];

export const defaultScenario = scenarios[0];
