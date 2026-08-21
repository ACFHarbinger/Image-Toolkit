# rust_parser — Rust source parser plugin

A D52 command plugin (#423): extracts symbols (fn / struct / enum / trait /
impl / mod / use / const / static / type) from a workspace's .rs files with a
lightweight std-only tokenizer, and feeds them to devtool as artifacts (#410
shape) and devtool.record-shaped records (#409).

- Parser: std-only tokenizer (no external crates; cargo network access is not
  assumed, so the build stays hermetic). Genuine symbol extraction, not a
  full grammar.
- Wire: frozen D52 JSON-RPC-over-stdio (initialize / list_artifacts /
  list_records / ping; host appends --stdio, Grok lock #8).
- Scan root: --root <dir> or cwd (host spawns from the workspace root).

## Build + smoke check

    cargo build --release --offline --manifest-path dev/plugins/rust_parser/Cargo.toml
    printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize"}' | \
      dev/plugins/rust_parser/target/release/rust_parser --stdio --root dev/
