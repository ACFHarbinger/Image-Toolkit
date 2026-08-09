# Function: zScoreNormalize()

> **zScoreNormalize**(`xs`): `number`[]

Defined in: [stats.ts:149](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/stats.ts#L149)

Z-score normalise (subtract mean, divide by std dev).
Returns all-zeros for constant arrays.

## Parameters

### xs

`number`[]

Input values.

## Returns

`number`[]

Array of z-scores (zero mean, unit variance).
