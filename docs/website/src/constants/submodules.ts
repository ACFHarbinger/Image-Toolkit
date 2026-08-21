// Hand-authored — the sibling repos under submodules/, each
// with its own docs/website/ built from this architecture.
import type { SubmoduleSite } from "../interfaces/types";

export const submoduleSites: SubmoduleSite[] = [
  {
    slug: "anime-stitch-pipeline",
    title: "Anime-Stitch-Pipeline",
    description: "Anime panorama stitching engine (ASP) with 2D motion estimation, GNC-TLS, and cel seam barriers.",
    url: "https://acfharbinger.github.io/Anime-Stitch-Pipeline/app/",
    repo: "https://github.com/ACFHarbinger/Anime-Stitch-Pipeline",
  },
  {
    slug: "cel-shaded-generator",
    title: "Cel-Shaded-Generator",
    description: "Manga lineart colorization, mesh overlay, animation & puppeteering (CSG).",
    url: "https://acfharbinger.github.io/Cel-Shaded-Generator/app/",
    repo: "https://github.com/ACFHarbinger/Cel-Shaded-Generator",
  },
  {
    slug: "content-recommendation-engine",
    title: "Content-Recommendation-Engine",
    description: "Local-first hybrid vector recommendation engine (CRE) using pgvector.",
    url: "https://acfharbinger.github.io/Content-Recommendation-Engine/app/",
    repo: "https://github.com/ACFHarbinger/Content-Recommendation-Engine",
  },
  {
    slug: "hybrid-image-editor",
    title: "Hybrid-Image-Editor",
    description: "Machine Learning (BiRefNet, Inpainting), RL Brush Assistant & Optimization engine (HIE).",
    url: "https://acfharbinger.github.io/Hybrid-Image-Editor/app/",
    repo: "https://github.com/ACFHarbinger/Hybrid-Image-Editor",
  },
];
