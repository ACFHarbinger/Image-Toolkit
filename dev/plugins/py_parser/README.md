# py_parser — Python source parser plugin

A D52 command plugin (#423): extracts symbols (functions, async functions,
classes, imports, module-level assignments) from a workspace's .py files
using the standard library ast module, and feeds them to devtool as
artifacts (#410 shape) and devtool.record-shaped records (#409).

- Parser: stdlib ast (the language's real parser, zero dependencies).
- Wire: frozen D52 JSON-RPC-over-stdio (initialize / list_artifacts /
  list_records / ping; host appends --stdio, Grok lock #8).
- Scan root: --root <dir> or cwd (host spawns from the workspace root).

## Smoke check

    printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize"}' \
      '{"jsonrpc":"2.0","id":2,"method":"list_artifacts"}' | \
      .venv/bin/python dev/plugins/py_parser/parser.py --stdio --root dev/
