# d52_proof — the D52 language-neutrality proof plugin

A tiny, dependency-free Go binary that proves the plugin process protocol is
genuinely language-neutral (D52, `docs/moon/roadmaps/development_tool.md`).
The host spawns it as `d52_proof --stdio` (Grok lock #8: the command entry is
the argv; the host appends `--stdio`) and speaks newline-delimited JSON-RPC 2.0
on that process's stdin/stdout.

This plugin needs no Python, no Image-Toolkit package, and no Go modules
beyond the standard library. A plugin author in a *different* repo can ship a
plugin with only (a) a `plugin.json` manifest with a `command` entry and (b)
this binary shape.

## Frozen contract

The JSON-RPC methods are the frozen contract. Every command plugin must answer
at minimum `initialize` and `list_artifacts`; this proof also answers `ping`:

| method          | response result                                            |
| --------------- | ---------------------------------------------------------- |
| `initialize`    | `{protocolVersion, capabilities, serverInfo}`              |
| `list_artifacts`| `{artifacts: [{kind, name, path, meta}...]}` (#410 shape)  |
| `ping`          | `{}`                                                       |

Errors follow JSON-RPC 2.0: `-32700` parse error (id `null`), `-32601`
method-not-found, `-32600` malformed request. Notifications (no `id`) get no
response. The process exits `0` on stdin EOF; it exits `2` if launched without
`--stdio`.

## Build + test

```sh
go build -o bin/d52_proof .
go test ./...
```

The built binary lives in `bin/` (gitignored). The in-tree manifest at
`dev/tool/plugins/d52_proof.plugin.json` references the binary by a
repo-root-relative argv (`dev/plugins/d52_proof/bin/d52_proof`), matching the
existing first-party manifests' convention (e.g. `benchmarks` uses
`.venv/bin/python`). The pytest integration test
(`dev/test/development/test_d52_proof.py`) builds the binary to a temp dir and
spawns it directly, so it does not depend on a prebuilt `bin/`.

## Manual smoke check

```sh
go build -o bin/d52_proof .
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize"}' \
  '{"jsonrpc":"2.0","id":2,"method":"list_artifacts"}' | ./bin/d52_proof --stdio
```