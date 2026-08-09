# Class: Graph

Defined in: [graph.ts:21](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/graph.ts#L21)

## Constructors

### Constructor

> **new Graph**(`directed?`): `Graph`

Defined in: [graph.ts:26](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/graph.ts#L26)

#### Parameters

##### directed?

`boolean` = `true`

#### Returns

`Graph`

## Properties

### adj

> `readonly` **adj**: `Map`\<`string`, [`GraphEdge`](/api/typescript/interfaces/GraphEdge)[]\>

Defined in: [graph.ts:23](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/graph.ts#L23)

***

### directed

> `readonly` **directed**: `boolean`

Defined in: [graph.ts:24](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/graph.ts#L24)

***

### nodes

> `readonly` **nodes**: `Map`\<`string`, [`GraphNode`](/api/typescript/interfaces/GraphNode)\>

Defined in: [graph.ts:22](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/graph.ts#L22)

## Accessors

### nodeCount

#### Get Signature

> **get** **nodeCount**(): `number`

Defined in: [graph.ts:54](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/graph.ts#L54)

##### Returns

`number`

## Methods

### addEdge()

> **addEdge**(`edge`): `void`

Defined in: [graph.ts:35](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/graph.ts#L35)

#### Parameters

##### edge

[`GraphEdge`](/api/typescript/interfaces/GraphEdge)

#### Returns

`void`

***

### addNode()

> **addNode**(`node`): `void`

Defined in: [graph.ts:30](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/graph.ts#L30)

#### Parameters

##### node

[`GraphNode`](/api/typescript/interfaces/GraphNode)

#### Returns

`void`

***

### neighbors()

> **neighbors**(`id`): [`GraphEdge`](/api/typescript/interfaces/GraphEdge)[]

Defined in: [graph.ts:46](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/graph.ts#L46)

#### Parameters

##### id

`string`

#### Returns

[`GraphEdge`](/api/typescript/interfaces/GraphEdge)[]

***

### nodeIds()

> **nodeIds**(): `string`[]

Defined in: [graph.ts:50](https://github.com/ACFHarbinger/Image-Toolkit/blob/c83b0f03024b40295257ca9a82367a60fe0f1ce2/frontend/src/math/graph.ts#L50)

#### Returns

`string`[]
