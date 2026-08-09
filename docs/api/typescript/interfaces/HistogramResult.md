# Interface: HistogramResult

Defined in: [stats.ts:156](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/stats.ts#L156)

Result object returned by [histogram](/api/typescript/functions/histogram).

## Properties

### counts

> **counts**: `number`[]

Defined in: [stats.ts:160](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/stats.ts#L160)

Integer count per bin, length = `bins`.

***

### edges

> **edges**: `number`[]

Defined in: [stats.ts:158](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/stats.ts#L158)

Bin edge values, length = `bins + 1`.

***

### probs

> **probs**: `number`[]

Defined in: [stats.ts:162](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/stats.ts#L162)

Probability (count / total) per bin, length = `bins`.
