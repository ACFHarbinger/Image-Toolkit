import { Brush, Film, Layers3 } from "lucide-react";

export const site = {
  shortName: "CSG",
  name: "Cel-Shaded Generator",
  eyebrow: "MANGA COLOR / ART ASSISTANT",
  badge: "CEL LAB / v1.0",
  heroTitle: ["Shape the", "frame."],
  heroDescription: "A visual-generation and learning workspace for manga colorization, cel-shaded rendering, deformation-aware art assistance, and animation-ready workflows.",
  accent: "rose",
  repository: "https://github.com/ACFHarbinger/Cel-Shaded-Generator",
  modules: [
    { number: "01", title: "Preserve the Line", text: "Keep line art, masks, and palette decisions explicit throughout colorization.", detail: "The drawing remains the source of truth while assistance stays reversible.", action: "Read the architecture", href: "https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/docs/ARCHITECTURE.md", icon: Brush },
    { number: "02", title: "Guide the Style", text: "Use references and controlled transformations to shape a cel-shaded visual language.", detail: "Style guidance is inspectable instead of being a black-box prompt result.", action: "Inspect the pipeline", href: "#pipeline", icon: Layers3 },
    { number: "03", title: "Think in Motion", text: "Prepare deformation and temporal-consistency workflows for animation.", detail: "Still-art tools are designed with frame sequences in mind.", action: "Read the project format", href: "https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/docs/project_format.md", icon: Film },
  ],
  stages: ["INGEST", "MASK", "COLOR", "STYLE", "WARP", "ANIMATE"],
};
