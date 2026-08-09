# Function: zScoreNormalize()

> **zScoreNormalize**(`xs`): `number`[]

Defined in: [stats.ts:149](https://github.com/ACFHarbinger/Image-Toolkit/blob/9190541af071250910b565c74fabdf538a60aa6c/frontend/src/math/stats.ts#L149)

Z-score normalise (subtract mean, divide by std dev).
Returns all-zeros for constant arrays.

## Parameters

### xs

`number`[]

Input values.

## Returns

`number`[]

Array of z-scores (zero mean, unit variance).
