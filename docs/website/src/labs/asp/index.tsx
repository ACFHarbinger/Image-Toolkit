import { Camera, GitBranch, ScanLine } from "lucide-react";
import { documentsFromGlob, LabDocs, LabHome, LabPipeline, type LabSite } from "../shared/LabPages";

const raw = {
  ...import.meta.glob("../../../../guides/stitching*.md", { query: "?raw", import: "default", eager: true }),
  ...import.meta.glob("../../../../moon/roadmaps/stitching*.md", { query: "?raw", import: "default", eager: true }),
  ...import.meta.glob("../../../../moon/research/stitching*.md", { query: "?raw", import: "default", eager: true }),
  ...import.meta.glob("../../../../moon/reports/stitching*.md", { query: "?raw", import: "default", eager: true }),
  ...import.meta.glob("../../../../moon/stitching*.md", { query: "?raw", import: "default", eager: true }),
  ...import.meta.glob("../../../../adr/stitching*.md", { query: "?raw", import: "default", eager: true }),
  ...import.meta.glob("../../../../tutorials/stitching*.md", { query: "?raw", import: "default", eager: true }),
  ...import.meta.glob("../../../../sphinx/stitching*", { query: "?raw", import: "default", eager: true }),
  ...import.meta.glob("../../../../modules/stitching-LICENSE", { query: "?raw", import: "default", eager: true }),
} as Record<string, string>;

const site: LabSite = {
  slug: "asp",
  shortName: "ASP",
  name: "Anime Stitch Pipeline",
  eyebrow: "PANORAMA STITCHING / VISUAL STRUCTURE",
  badge: "STITCH LAB / v2.0",
  heroTitle: ["Trace the", "unseen."],
  heroDescription:
    "A high-performance panorama engine for anime panning shots, built around constrained motion, robust estimation, seam-aware compositing, and honest evaluation.",
  accent: "cyan",
  repository: "https://github.com/ACFHarbinger/Image-Toolkit/tree/main/docs/guides",
  originalRepository: "https://github.com/ACFHarbinger/Anime-Stitch-Pipeline",
  modules: [
    {
      number: "01",
      title: "Capture & Index",
      text: "Keep source frames, references, and provenance attached from ingestion onward.",
      detail: "Build a searchable sequence workspace before alignment begins.",
      action: "Read the architecture",
      href: "/labs/asp/docs/guides/stitching-architecture.md",
      icon: Camera,
    },
    {
      number: "02",
      title: "Align Structure",
      text: "Estimate constrained 2D motion and reject unstable feature matches.",
      detail: "GNC-TLS residual weighting and bundle adjustment make the signal inspectable.",
      action: "Inspect the pipeline",
      href: "/labs/asp/pipeline",
      icon: ScanLine,
    },
    {
      number: "03",
      title: "Compose Evidence",
      text: "Route seams around protected cel regions and preserve review artifacts.",
      detail: "Render panoramas with seam diagnostics instead of hiding quality behind one score.",
      action: "Read the benchmarks",
      href: "/labs/asp/docs/guides/stitching-benchmarks.md",
      icon: GitBranch,
    },
  ],
  stages: ["INGEST", "MATCH", "GNC-TLS", "BUNDLE", "SEAM", "RENDER"],
  documents: documentsFromGlob(raw),
};

export function AspHome() {
  return <LabHome site={site} />;
}

export function AspPipeline() {
  return <LabPipeline site={site} />;
}

export function AspDocs() {
  return <LabDocs site={site} />;
}
