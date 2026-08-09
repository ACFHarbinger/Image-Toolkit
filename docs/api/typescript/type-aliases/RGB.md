# Type Alias: RGB

> **RGB** = \[`number`, `number`, `number`\]

Defined in: [colormap.ts:7](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/colormap.ts#L7)

Perceptually-uniform colormaps for analytics visualisations.

 Each colormap maps a scalar t ∈ [0, 1] to an `[R, G, B]` triple in [0, 255].
 Implementations use the reference lookup tables from matplotlib 3.x (17-stop
 down-sampled; linear interpolation between stops is accurate to ±2/255).
