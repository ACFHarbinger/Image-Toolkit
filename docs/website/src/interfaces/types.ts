export interface NavLeaf {
  title: string;
  kind: "md";
  path: string;
  source: string;
}
export interface NavExternal {
  title: string;
  kind: "external";
  href: string;
}
export interface NavSection {
  title: string;
  kind: "section";
  children: NavNode[];
}
export type NavNode = NavLeaf | NavExternal | NavSection;

export interface SearchEntry {
  title: string;
  path: string;
  source: string;
}

export interface ModuleCard {
  slug: string;
  title: string;
  tagline: string;
  description: string;
  stack: string[];
  path: string;
  docSource?: string;
  layer: "engine" | "interface" | "data" | "security";
}

export interface SubmoduleSite {
  slug: string;
  title: string;
  description: string;
  url: string;
  repo: string;
}

export interface BenchmarkStat {
  label: string;
  value: string;
  detail: string;
}

export interface BenchmarkSuite {
  suite: string;
  runner: string;
  location: string;
  output: string;
  ciJob: string;
}

export interface RoadmapCard {
  slug: string;
  title: string;
  summary: string;
  path: string;
  docSource: string;
}
