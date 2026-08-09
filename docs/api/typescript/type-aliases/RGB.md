# Type Alias: RGB

> **RGB** = \[`number`, `number`, `number`\]

Defined in: [colormap.ts:7](https://github.com/ACFHarbinger/Image-Toolkit/blob/9190541af071250910b565c74fabdf538a60aa6c/frontend/src/math/colormap.ts#L7)

Perceptually-uniform colormaps for analytics visualisations.

 Each colormap maps a scalar t ∈ [0, 1] to an `[R, G, B]` triple in [0, 255].
 Implementations use the reference lookup tables from matplotlib 3.x (17-stop
 down-sampled; linear interpolation between stops is accurate to ±2/255).
