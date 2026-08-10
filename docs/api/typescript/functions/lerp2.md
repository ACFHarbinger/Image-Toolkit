# Function: lerp2()

> **lerp2**(`a`, `b`, `t`): [`Vec2`](/api/typescript/type-aliases/Vec2)

Defined in: [linalg.ts:55](https://github.com/ACFHarbinger/Image-Toolkit/blob/151030dce5d66210a825506a38d724662270bc79/frontend/src/math/linalg.ts#L55)

Linear interpolation between two 2D vectors.

## Parameters

### a

[`Vec2`](/api/typescript/type-aliases/Vec2)

Start vector (t=0).

### b

[`Vec2`](/api/typescript/type-aliases/Vec2)

End vector (t=1).

### t

`number`

Interpolation parameter. Clamp to [0,1] for in-range results.

## Returns

[`Vec2`](/api/typescript/type-aliases/Vec2)
