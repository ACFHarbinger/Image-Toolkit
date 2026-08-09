# Function: histogram()

> **histogram**(`xs`, `bins`): [`HistogramResult`](/api/typescript/interfaces/HistogramResult)

Defined in: [stats.ts:177](https://github.com/ACFHarbinger/Image-Toolkit/blob/9190541af071250910b565c74fabdf538a60aa6c/frontend/src/math/stats.ts#L177)

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
