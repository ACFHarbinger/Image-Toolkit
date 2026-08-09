# Function: euclidean()

> **euclidean**(`a`, `b`): `number`

Defined in: [distance.ts:36](https://github.com/ACFHarbinger/Image-Toolkit/blob/9190541af071250910b565c74fabdf538a60aa6c/frontend/src/math/distance.ts#L36)

Euclidean (L2) distance.

## Parameters

### a

`number`[]

First vector.

### b

`number`[]

Second vector. Must have the same length as `a`.

## Returns

`number`

L2 distance ≥ 0.

## Example

```ts
euclidean([0, 0], [3, 4]); // 5
```
