# Function: hammingDistance()

> **hammingDistance**(`a`, `b`): `number`

Defined in: [distance.ts:97](https://github.com/ACFHarbinger/Image-Toolkit/blob/151030dce5d66210a825506a38d724662270bc79/frontend/src/math/distance.ts#L97)

Hamming distance: count of positions where values differ.
Suitable for binary or integer vectors.

## Parameters

### a

`number`[]

First vector.

### b

`number`[]

Second vector. Must have the same length as `a`.

## Returns

`number`

Number of differing positions ∈ [0, a.length].

## Example

```ts
hammingDistance([1, 0, 1], [1, 1, 1]); // 1
```
