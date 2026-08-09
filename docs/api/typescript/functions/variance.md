# Function: variance()

> **variance**(`xs`): `number`

Defined in: [stats.ts:32](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/stats.ts#L32)

Population variance (divides by N).

## Parameters

### xs

`number`[]

Input values. Returns 0 for arrays with fewer than 2 elements.

## Returns

`number`

Population variance ≥ 0.

## Example

```ts
variance([2, 4, 4, 4, 5, 5, 7, 9]); // 4
```
