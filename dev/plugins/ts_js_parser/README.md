# ts_js_parser — TypeScript/JavaScript source parser plugin

A D52 command plugin (#423): extracts symbols (interfaces, classes,
functions, enums, top-level const/let/var) from a workspace's TS/JS sources
using the TypeScript compiler API (ts.createSourceFile), and feeds them to
devtool as artifacts (#410 shape) and devtool.record-shaped records (#409).

- Parser: the TypeScript compiler API (resolves "typescript" from the
  consuming repo's node_modules; this monorepo ships it).
- Wire: frozen D52 JSON-RPC-over-stdio (initialize / list_artifacts /
  list_records / ping; host appends --stdio, Grok lock #8).
- Scan root: --root <dir> or cwd (host spawns from the workspace root).

## Smoke check

    printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize"}' | \
      node dev/plugins/ts_js_parser/parser.js --stdio --root dev/
