# Function: histogram()

> **histogram**(`xs`, `bins`): [`HistogramResult`](/api/typescript/interfaces/HistogramResult)

Defined in: [stats.ts:177](https://github.com/ACFHarbinger/Image-Toolkit/blob/151030dce5d66210a825506a38d724662270bc79/frontend/src/math/stats.ts#L177)

Equal-width histogram.

## Parameters

### xs

`number`[]

Input values.

### bins

`number`

Number of equal-width bins.

## Returns

[`HistogramResult`](/api/typescript/interfaces/HistogramResult)

`{ edges, counts, probs }` — see [HistogramResult](/api/typescript/interfaces/HistogramResult).

## Example

```ts
const h = histogram([1, 2, 3, 4], 2);
// h.edges ≈ [1, 2.5, 4]
// h.counts = [2, 2]
```
