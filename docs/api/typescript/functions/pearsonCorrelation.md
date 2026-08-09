# Function: pearsonCorrelation()

> **pearsonCorrelation**(`xs`, `ys`): `number`

Defined in: [stats.ts:120](https://github.com/ACFHarbinger/Image-Toolkit/blob/9190541af071250910b565c74fabdf538a60aa6c/frontend/src/math/stats.ts#L120)

Pearson correlation coefficient ∈ [−1, 1].
Returns 0 when either array has zero standard deviation.

## Parameters

### xs

`number`[]

First array of values.

### ys

`number`[]

Second array of values. Must have the same length as `xs`.

## Returns

`number`

Pearson r ∈ [−1, 1], or 0 for constant inputs.

## Example

```ts
pearsonCorrelation([1, 2, 3], [1, 2, 3]); // ~1.0
pearsonCorrelation([1, 2, 3], [3, 2, 1]); // ~-1.0
```
