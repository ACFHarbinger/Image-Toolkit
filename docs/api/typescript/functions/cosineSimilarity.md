# Function: cosineSimilarity()

> **cosineSimilarity**(`a`, `b`): `number`

Defined in: [distance.ts:70](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/distance.ts#L70)

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
