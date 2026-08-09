# Function: pairwiseDistances()

> **pairwiseDistances**(`points`, `distFn?`): `number`[][]

Defined in: [distance.ts:112](https://github.com/ACFHarbinger/Image-Toolkit/blob/9190541af071250910b565c74fabdf538a60aa6c/frontend/src/math/distance.ts#L112)

Compute the full N×N pairwise distance matrix.
The matrix is symmetric with zeros on the diagonal.

## Parameters

### points

`number`[][]

Array of N vectors (all must have the same dimensionality).

### distFn?

(`a`, `b`) => `number`

Distance function to apply. Defaults to `euclidean`.

## Returns

`number`[][]

N×N matrix where `result[i][j]` is the distance between `points[i]` and `points[j]`.

## Example

```ts
pairwiseDistances([[0, 0], [3, 4], [0, 4]]);
// [[0, 5, 4], [5, 0, 3], [4, 3, 0]]
```
