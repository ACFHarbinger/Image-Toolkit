// Hand-authored (not generated) — the sibling repos under submodules/, each
// with its own docs/website/ built from this same architecture, deployed to
// its own GitHub Pages. Embedded here via iframe (SubmodulePage.vue) so
// they're reachable without leaving this site's chrome.
import type { SubmoduleSite } from "../interfaces/types";

export const submoduleSites: SubmoduleSite[] = [
  {
    slug: "anime-stitch-pipeline",
    title: "Anime-Stitch-Pipeline",
    description: "Anime panorama stitching engine (ASP).",
    url: "https://acfharbinger.github.io/Anime-Stitch-Pipeline/app/",
    repo: "https://github.com/ACFHarbinger/Anime-Stitch-Pipeline",
  },
  {
    slug: "cel-shaded-generator",
    title: "Cel-Shaded-Generator",
    description: "Manga colorization & animation (CSG).",
    url: "https://acfharbinger.github.io/Cel-Shaded-Generator/app/",
    repo: "https://github.com/ACFHarbinger/Cel-Shaded-Generator",
  },
  {
    slug: "content-recommendation-engine",
    title: "Content-Recommendation-Engine",
    description: "Local-first hybrid vector recommendation engine (CRE).",
    url: "https://acfharbinger.github.io/Content-Recommendation-Engine/app/",
    repo: "https://github.com/ACFHarbinger/Content-Recommendation-Engine",
  },
];
