# Function: hammingDistance()

> **hammingDistance**(`a`, `b`): `number`

Defined in: [distance.ts:97](https://github.com/ACFHarbinger/Image-Toolkit/blob/9190541af071250910b565c74fabdf538a60aa6c/frontend/src/math/distance.ts#L97)

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
