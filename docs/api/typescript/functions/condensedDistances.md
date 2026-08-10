# Function: condensedDistances()

> **condensedDistances**(`points`, `distFn?`): `number`[]

Defined in: [distance.ts:140](https://github.com/ACFHarbinger/Image-Toolkit/blob/151030dce5d66210a825506a38d724662270bc79/frontend/src/math/distance.ts#L140)

Condensed upper-triangle distance vector.
Compatible with SciPy `linkage` input format (row-major upper triangle, no diagonal).

## Parameters

### points

`number`[][]

Array of N vectors.

### distFn?

(`a`, `b`) => `number`

Distance function to apply. Defaults to `euclidean`.

## Returns

`number`[]

Array of N*(N-1)/2 distances in row-major upper-triangle order.

## Example

```ts
// For 3 points → [d(0,1), d(0,2), d(1,2)]
condensedDistances([[0,0],[1,0],[0,1]]).length; // 3
```
