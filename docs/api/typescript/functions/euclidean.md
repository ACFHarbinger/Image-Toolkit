# Function: euclidean()

> **euclidean**(`a`, `b`): `number`

Defined in: [distance.ts:36](https://github.com/ACFHarbinger/Image-Toolkit/blob/151030dce5d66210a825506a38d724662270bc79/frontend/src/math/distance.ts#L36)

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
