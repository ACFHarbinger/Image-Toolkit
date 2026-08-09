// Sourced from docs/mkdocs.yml's "Roadmaps" nav section (the feature-roadmap
// docs actually listed there — see docs/moon/roadmaps/) — feeds the
// Roadmap hub panel. Paths mirror generate-nav.mjs's slugify() output.
import type { RoadmapCard } from "../interfaces/types";

export const roadmapCards: RoadmapCard[] = [
  {
    slug: "architecture",
    title: "Architecture & Infrastructure",
    summary: "Quality, reliability, and maintainability across the polyglot module boundary.",
    path: "/roadmaps/architecture",
    docSource: "docs/moon/roadmaps/architecture.md",
  },
  {
    slug: "performance",
    title: "Performance",
    summary: "Compute, memory, and I/O — from the C++ core to the pgvector query path.",
    path: "/roadmaps/performance",
    docSource: "docs/moon/roadmaps/performance.md",
  },
  {
    slug: "new-features",
    title: "New Features",
    summary: "Capabilities and integrations planned across the desktop, web, and mobile surfaces.",
    path: "/roadmaps/new_features",
    docSource: "docs/moon/roadmaps/new_features.md",
  },
  {
    slug: "gui-ux",
    title: "GUI / UX",
    summary: "Desktop interface quality and ergonomics for the PySide6 app.",
    path: "/roadmaps/gui_ux",
    docSource: "docs/moon/roadmaps/gui_ux.md",
  },
  {
    slug: "content-generation",
    title: "Content Generation",
    summary: "Anime image & video generation pipelines.",
    path: "/roadmaps/content_generation",
    docSource: "docs/moon/roadmaps/content_generation.md",
  },
  {
    slug: "analytics",
    title: "Analytics & Interpretability",
    summary: "Codebase topology, ML interpretability, pipeline diagnostics, and debugging.",
    path: "/roadmaps/analytics_and_interpretability",
    docSource: "docs/moon/roadmaps/analytics_and_interpretability.md",
  },
  {
    slug: "documentation",
    title: "Documentation",
    summary: "Docs-as-code, reference generation, and knowledge portals — including this site.",
    path: "/roadmaps/documentation",
    docSource: "docs/moon/roadmaps/documentation.md",
  },
];
