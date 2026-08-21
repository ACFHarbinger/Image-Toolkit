# Function: normalize01()

> **normalize01**(`xs`): `number`[]

Defined in: [stats.ts:136](https://github.com/ACFHarbinger/Image-Toolkit/blob/151030dce5d66210a825506a38d724662270bc79/frontend/src/math/stats.ts#L136)

Min-max normalise to [0, 1].
Returns all-zeros for constant arrays (zero range).

## Parameters

### xs

`number`[]

Input values.

## Returns

`number`[]

Array with each element rescaled to [0, 1].
