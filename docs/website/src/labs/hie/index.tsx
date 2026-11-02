import { BrainCircuit, Layers3, SlidersHorizontal } from "lucide-react";
import { documentsFromGlob, LabDocs, LabHome, LabPipeline, type LabSite } from "../shared/LabPages";

const raw = {
  ...import.meta.glob("../../../../editor/**/*.md", { query: "?raw", import: "default", eager: true }),
  ...import.meta.glob("../../../../editor/**/*.rst", { query: "?raw", import: "default", eager: true }),
  ...import.meta.glob("../../../../structurizr/editor/**/*.md", { query: "?raw", import: "default", eager: true }),
  ...import.meta.glob("../../../../structurizr/editor/**/*.dsl", { query: "?raw", import: "default", eager: true }),
} as Record<string, string>;

const site: LabSite = {
  slug: "hie",
  shortName: "HIE",
  name: "Hybrid Image Editor",
  eyebrow: "NON-DESTRUCTIVE / MULTI-MODAL EDITING",
  badge: "HYBRID LAB / v1.0",
  heroTitle: ["Make intent", "editable."],
  heroDescription:
    "A productive image-first editor combining a hybrid layer-node canvas, C++ optimization, neural models, reinforcement-learning policies, and reproducible pipeline jobs.",
  accent: "violet",
  repository: "https://github.com/ACFHarbinger/Image-Toolkit/tree/main/docs/editor",
  originalRepository: "https://github.com/ACFHarbinger/Hybrid-Image-Editor",
  modules: [
    {
      number: "01",
      title: "Document Intent",
      text: "Combine familiar layers with optional non-destructive modifier graphs.",
      detail: "Images are one-frame sequences from day one, ready for future video work.",
      action: "Read the architecture",
      href: "/labs/hie/docs/ARCHITECTURE.md",
      icon: Layers3,
    },
    {
      number: "02",
      title: "Assist the Artist",
      text: "Compose models and RL policies into inspectable editing proposals.",
      detail: "Localized retouching leads the policy sequence, followed by tone and composition.",
      action: "Inspect the middleware",
      href: "/labs/hie/docs/moon/roadmaps/04_middleware_and_ui_integration.md",
      icon: BrainCircuit,
    },
    {
      number: "03",
      title: "Solve the Work",
      text: "Run exact, swarm, and evolutionary optimization as cancellable jobs.",
      detail: "Every accepted operation keeps configuration, progress, and provenance.",
      action: "Read the roadmap",
      href: "/labs/hie/docs/moon/ROADMAP.md",
      icon: SlidersHorizontal,
    },
  ],
  stages: ["DOCUMENT", "MODEL", "POLICY", "JOB", "PREVIEW", "COMMIT"],
  documents: documentsFromGlob(raw, "editor"),
};

export function HieHome() {
  return <LabHome site={site} />;
}

export function HiePipeline() {
  return <LabPipeline site={site} />;
}

export function HieDocs() {
  return <LabDocs site={site} />;
}
