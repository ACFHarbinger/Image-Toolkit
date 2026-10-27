// GENERATED — contract hash 35537ebccd17268699e0134e7765a44288a13d2edf300ce1e33770aeee8d3856. Do not edit; edit the schema and regenerate.

export interface CompareItem {
  readonly path: string;
  readonly width: number;
  readonly height: number;
  readonly ahash: string;
  readonly error: string;
}
export interface ComparePair {
  readonly left: string;
  readonly right: string;
  readonly distance: number;
}
export interface CompareParams {
  readonly paths: Array<string>;
  readonly threshold: number;
}
export interface CompareResult {
  readonly items: Array<CompareItem>;
  readonly pairs: Array<ComparePair>;
}
export interface SimilarityScanParams {
  readonly directory: string;
  readonly threshold: number;
}
