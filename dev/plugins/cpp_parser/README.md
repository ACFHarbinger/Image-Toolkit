# cpp_parser — C/C++ source parser plugin

A D52 command plugin (#423): extracts symbols (class / struct / enum /
namespace / using / typedef / function signatures / #include) from a
workspace's C/C++ sources with a std-only tokenizer, and feeds them to
devtool as artifacts (#410 shape) and devtool.record-shaped records (#409).

- Parser: std-only tokenizer compiled with g++ (no libclang headers assumed,
  so the build stays hermetic). Genuine symbol extraction, not a full grammar.
- Wire: frozen D52 JSON-RPC-over-stdio (initialize / list_artifacts /
  list_records / ping; host appends --stdio, Grok lock #8).
- Scan root: --root <dir> or cwd (host spawns from the workspace root).

## Build + smoke check

    g++ -O2 -std=c++17 -o dev/plugins/cpp_parser/bin/cpp_parser dev/plugins/cpp_parser/main.cpp
    printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize"}' | \
      dev/plugins/cpp_parser/bin/cpp_parser --stdio --root dev/
