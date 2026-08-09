# Function: fruchtermanReingold()

> **fruchtermanReingold**(`g`, `opts?`): [`LayoutNode`](/api/typescript/interfaces/LayoutNode)[]

Defined in: [graph.ts:125](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/graph.ts#L125)

Fruchterman-Reingold force-directed layout.

Returns `{id, x, y}` for every node in the graph.  Coordinates are in
`[0, width] × [0, height]`.  Used for the Phase 1 AST dependency graph.

## Parameters

### g

[`Graph`](/api/typescript/classes/Graph)

### opts?

[`FROptions`](/api/typescript/interfaces/FROptions) = `{}`

## Returns

[`LayoutNode`](/api/typescript/interfaces/LayoutNode)[]
