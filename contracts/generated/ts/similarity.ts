// GENERATED — contract hash 653032d8e300ffda76d5ce42c68053ca1c26001221cde7b7e609718d8a3f829a. Do not edit; edit the schema and regenerate.

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
