// GENERATED — contract hash 8f3b63259aeee332f0b0ef1780647fdc1e5692c6d3e1a1d6b8b0aeb24360f303. Do not edit; edit the schema and regenerate.

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
