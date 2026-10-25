// GENERATED — contract hash c9734dc6d1b29f88e7c9975cc142965a3f7cdc5c5c907e455625999b987bc515. Do not edit; edit the schema and regenerate.

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
