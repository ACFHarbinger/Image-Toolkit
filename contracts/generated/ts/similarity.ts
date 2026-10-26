// GENERATED — contract hash 9de51fd76cff26625db8bc02d1154d1664e095d6d5e14f6349c28a223d5ca512. Do not edit; edit the schema and regenerate.

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
