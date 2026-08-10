# Function: zScoreNormalize()

> **zScoreNormalize**(`xs`): `number`[]

Defined in: [stats.ts:149](https://github.com/ACFHarbinger/Image-Toolkit/blob/151030dce5d66210a825506a38d724662270bc79/frontend/src/math/stats.ts#L149)

Z-score normalise (subtract mean, divide by std dev).
Returns all-zeros for constant arrays.

## Parameters

### xs

`number`[]

Input values.

## Returns

`number`[]

Array of z-scores (zero mean, unit variance).
