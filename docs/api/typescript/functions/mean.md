# Function: mean()

> **mean**(`xs`): `number`

Defined in: [stats.ts:20](https://github.com/ACFHarbinger/Image-Toolkit/blob/151030dce5d66210a825506a38d724662270bc79/frontend/src/math/stats.ts#L20)

Arithmetic mean of a number array.

## Parameters

### xs

`number`[]

Input values. Must be non-empty or NaN is returned.

## Returns

`number`

Mean, or `NaN` for empty input.

## Example

```ts
mean([1, 2, 3]); // 2
mean([]);        // NaN
```
