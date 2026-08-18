# java_kotlin_parser — Java/Kotlin source parser plugin

A D52 command plugin (#423): extracts symbols from a workspace's Java and
Kotlin sources and feeds them to devtool as artifacts (#410 shape) and
devtool.record-shaped records (#409).

- Parser: Java is parsed with the real javac AST (com.sun.source /
  JavacTask — the compiler's own parser, available in any JDK); Kotlin uses
  a lightweight tokenizer (kotlinc ships no public tree API in this shape).
  Both extract classes/methods/fields/imports plus per-file metrics.
- Wire: frozen D52 JSON-RPC-over-stdio (initialize / list_artifacts /
  list_records / ping; host appends --stdio, Grok lock #8).
- Scan root: --root <dir> or cwd (host spawns from the workspace root).

## Build + smoke check

    javac -d dev/plugins/java_kotlin_parser/bin dev/plugins/java_kotlin_parser/Parser.java
    printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize"}' | \
      java -cp dev/plugins/java_kotlin_parser/bin Parser --stdio --root dev/
