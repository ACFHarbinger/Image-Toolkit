// Hand-authored (not generated) — Image-Toolkit and its sibling repos under
// submodules/, each with its own docs/website/ built from this exact same
// source, deployed to its own GitHub Pages at <repo>/app/. Embedded here via
// iframe so they're reachable without leaving this site's chrome.
export interface SubmoduleSite {
  slug: string;
  title: string;
  description: string;
  url: string;
  repo: string;
}

export const submoduleSites: SubmoduleSite[] = [
  {
    slug: "image-toolkit",
    title: "Image-Toolkit",
    description: "Parent project — image database and edit toolkit.",
    url: "https://acfharbinger.github.io/Image-Toolkit/app/",
    repo: "https://github.com/ACFHarbinger/Image-Toolkit",
  },
  {
    slug: "anime-stitch-pipeline",
    title: "ASP",
    description: "Anime panorama stitching engine (ASP).",
    url: "https://acfharbinger.github.io/Anime-Stitch-Pipeline/app/",
    repo: "https://github.com/ACFHarbinger/Anime-Stitch-Pipeline",
  },
  {
    slug: "recommendation-engine",
    title: "CRE",
    description: "Local-first hybrid vector recommendation engine.",
    url: "https://acfharbinger.github.io/Content-Recommendation-Engine/app/",
    repo: "https://github.com/ACFHarbinger/Content-Recommendation-Engine",
  },
];
