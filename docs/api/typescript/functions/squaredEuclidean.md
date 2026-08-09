# Function: squaredEuclidean()

> **squaredEuclidean**(`a`, `b`): `number`

Defined in: [distance.ts:23](https://github.com/ACFHarbinger/Image-Toolkit/blob/9190541af071250910b565c74fabdf538a60aa6c/frontend/src/math/distance.ts#L23)

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
