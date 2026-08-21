# Function: squaredEuclidean()

> **squaredEuclidean**(`a`, `b`): `number`

Defined in: [distance.ts:23](https://github.com/ACFHarbinger/Image-Toolkit/blob/151030dce5d66210a825506a38d724662270bc79/frontend/src/math/distance.ts#L23)

Squared Euclidean distance — cheaper than `euclidean` when only relative
ordering matters (avoids the square root).

## Parameters

### a

`number`[]

First vector.

### b

`number`[]

Second vector. Must have the same length as `a`.

## Returns

`number`

Sum of squared element-wise differences ≥ 0.

## Example

```ts
squaredEuclidean([0, 0], [3, 4]); // 25
```
