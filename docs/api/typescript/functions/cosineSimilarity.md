# Function: cosineSimilarity()

> **cosineSimilarity**(`a`, `b`): `number`

Defined in: [distance.ts:70](https://github.com/ACFHarbinger/Image-Toolkit/blob/151030dce5d66210a825506a38d724662270bc79/frontend/src/math/distance.ts#L70)

Cosine similarity ∈ [−1, 1].
Returns 0 for zero vectors (no meaningful angle).

## Parameters

### a

`number`[]

First vector.

### b

`number`[]

Second vector. Must have the same length as `a`.

## Returns

`number`

Cosine similarity ∈ [−1, 1].

## Example

```ts
cosineSimilarity([1, 0], [1, 0]); // 1.0 (identical direction)
cosineSimilarity([1, 0], [0, 1]); // 0.0 (orthogonal)
cosineSimilarity([1, 0], [-1, 0]); // -1.0 (opposite)
```
