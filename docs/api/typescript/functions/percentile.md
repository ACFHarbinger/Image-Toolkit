# Function: percentile()

> **percentile**(`xs`, `p`): `number`

Defined in: [stats.ts:87](https://github.com/ACFHarbinger/Image-Toolkit/blob/151030dce5d66210a825506a38d724662270bc79/frontend/src/math/stats.ts#L87)

Nearest-rank percentile (R-1 method).

## Parameters

### xs

`number`[]

Input values (need not be sorted).

### p

`number`

Percentile rank in [0, 1]. 0 → minimum, 0.5 → median, 1 → maximum.

## Returns

`number`

The value at the nearest-rank percentile, or `NaN` for empty input.

## Example

```ts
percentile([1, 2, 3, 4], 0.5); // 2 (nearest-rank median)
```
