#!/usr/bin/env node
// TypeScript/JavaScript source parser plugin (#423).
//
// A D52 command plugin: spawned by the host as
// "node dev/plugins/ts_js_parser/parser.js --stdio" (Grok lock #8: the
// manifest's entry.command is the argv; the host appends --stdio). Speaks
// the frozen JSON-RPC-over-stdio contract (initialize / list_artifacts /
// list_records / ping) and answers with REAL evidence about a workspace's
// TS/JS sources:
//
// - list_artifacts -> one artifact per scanned source file, #410 shape
//   {kind, name, path, meta}; meta carries {language, loc, symbols:[...]}.
// - list_records   -> devtool.record-shaped records (#409): one record per
//   extracted symbol (kind="symbol") plus one per file (kind="file").
//
// Parsing uses the TypeScript compiler API (ts.createSourceFile) -- the
// language's real parser, resolving "typescript" from the consuming repo's
// node_modules (this monorepo ships it). Symbols: functions, classes,
// interfaces, type aliases, enums, and top-level const/let/var declarations.
//
// Scan root: --root <dir> or cwd (the host spawns from the workspace root).
"use strict";

const fs = require("fs");
const path = require("path");
const ts = require("typescript");

const PROTOCOL_VERSION = "1";
const SERVER_NAME = "ts_js_parser";
const SERVER_VERSION = "0.1.0";
const EXTENSIONS = new Set([".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]);
const IGNORED_DIRS = new Set([
  ".git", ".venv", "node_modules", "target", "build", "dist", ".tox", "__pycache__",
]);

const RECORD_SCHEMA = "devtool.record";
const RECORD_SCHEMA_VERSION = 1;

function scanRootFromArgv(argv) {
  let root = process.cwd();
  const idx = argv.indexOf("--root");
  if (idx >= 0 && idx + 1 < argv.length) root = argv[idx + 1];
  return root;
}

function iterSourceFiles(root) {
  const out = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (!IGNORED_DIRS.has(entry.name)) walk(full);
      } else if (entry.isFile() && EXTENSIONS.has(path.extname(entry.name))) {
        out.push(full);
      }
    }
  };
  walk(root);
  out.sort();
  return out;
}

function symbolsFromSource(text, isTs) {
  const symbols = [];
  const sf = ts.createSourceFile("inline.ts", text, ts.ScriptTarget.Latest, true, isTs ? ts.ScriptKind.TS : ts.ScriptKind.JS);

  const add = (name, kind, line) => {
    const loc = sf.getLineAndCharacterOfPosition(line);
    symbols.push({ name, kind, line: loc.line + 1 });
  };

  const visit = (node) => {
    if (ts.isFunctionDeclaration(node) && node.name) {
      add(node.name.text, "function", node.name.getStart(sf));
    } else if (ts.isClassDeclaration(node) && node.name) {
      add(node.name.text, "class", node.name.getStart(sf));
    } else if (ts.isInterfaceDeclaration(node) && node.name) {
      add(node.name.text, "interface", node.name.getStart(sf));
    } else if (ts.isTypeAliasDeclaration(node) && node.name) {
      add(node.name.text, "type_alias", node.name.getStart(sf));
    } else if (ts.isEnumDeclaration(node) && node.name) {
      add(node.name.text, "enum", node.name.getStart(sf));
    } else if (ts.isVariableStatement(node)) {
      for (const decl of node.declarationList.declarations) {
        if (ts.isIdentifier(decl.name)) {
          add(decl.name.text, "variable", decl.name.getStart(sf));
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
  return symbols;
}

function scan(root) {
  const files = [];
  const symbols = [];
  for (const file of iterSourceFiles(root)) {
    let text = "";
    try {
      text = fs.readFileSync(file, "utf8");
    } catch (err) {
      continue;
    }
    const isTs = /^\.tsx?$/.test(path.extname(file));
    const syms = symbolsFromSource(text, isTs);
    files.push({
      path: file,
      rel: path.relative(root, file),
      loc: text.split("\n").length,
      symbols: syms,
    });
    for (const s of syms) {
      symbols.push(Object.assign({}, s, { file: path.relative(root, file) }));
    }
  }
  return { files, symbols };
}

class TsJsParserServer {
  constructor(root) {
    this.root = root;
    this._cache = null;
  }
  _data() {
    if (this._cache === null) this._cache = scan(this.root);
    return this._cache;
  }
  _listArtifacts() {
    return this._data().files.map((f) => ({
      kind: "source_file",
      name: f.rel,
      path: f.path,
      meta: { language: "typescript", loc: f.loc, symbols: f.symbols },
    }));
  }
  _listRecords() {
    const workspace = this.root;
    const records = [];
    for (const s of this._data().symbols) {
      records.push({
        schema: RECORD_SCHEMA,
        schema_version: RECORD_SCHEMA_VERSION,
        kind: "symbol",
        start_ms: 0.0,
        end_ms: null,
        source: SERVER_NAME,
        workspace,
        payload: {
          name: s.name,
          symbol_kind: s.kind,
          line: s.line,
          file: s.file,
          language: "typescript",
        },
      });
    }
    for (const f of this._data().files) {
      records.push({
        schema: RECORD_SCHEMA,
        schema_version: RECORD_SCHEMA_VERSION,
        kind: "file",
        start_ms: 0.0,
        end_ms: null,
        source: SERVER_NAME,
        workspace,
        payload: { file: f.rel, language: "typescript", loc: f.loc, symbol_count: f.symbols.length },
      });
    }
    return records;
  }
  handle(raw) {
    let msg;
    try {
      msg = JSON.parse(raw);
    } catch (err) {
      return JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "parse error" } });
    }
    if (typeof msg !== "object" || msg === null || !("id" in msg)) return null;
    const method = msg.method;
    const id = msg.id;
    if (method === "initialize") {
      return JSON.stringify({
        jsonrpc: "2.0", id,
        result: {
          protocolVersion: PROTOCOL_VERSION,
          capabilities: { artifacts: true, records: true },
          serverInfo: { name: SERVER_NAME, version: SERVER_VERSION },
        },
      });
    }
    if (method === "list_artifacts") {
      return JSON.stringify({ jsonrpc: "2.0", id, result: { artifacts: this._listArtifacts() } });
    }
    if (method === "list_records") {
      return JSON.stringify({ jsonrpc: "2.0", id, result: { records: this._listRecords() } });
    }
    if (method === "ping") {
      return JSON.stringify({ jsonrpc: "2.0", id, result: {} });
    }
    return JSON.stringify({
      jsonrpc: "2.0", id,
      error: { code: -32601, message: "method not found: " + method },
    });
  }
  serveStdio(stdin, stdout) {
    stdin = stdin || process.stdin;
    stdout = stdout || process.stdout;
    const rl = require("readline").createInterface({ input: stdin });
    rl.on("line", (line) => {
      line = line.trim();
      if (!line) return;
      const response = this.handle(line);
      if (response !== null) {
        stdout.write(response + "\n");
      }
    });
  }
}

function main(argv) {
  argv = argv || process.argv.slice(2);
  if (!argv.includes("--stdio")) {
    process.stderr.write("ts_js_parser: --stdio is required (Grok lock #8: the host appends it)\n");
    return 2;
  }
  const root = scanRootFromArgv(argv);
  new TsJsParserServer(root).serveStdio();
  return 0;
}

if (require.main === module) {
  const code = main();
  if (code !== 0) process.exit(code);
  // The stdio server keeps the event loop alive until stdin EOF; only the
  // --stdio error path (code 2) exits synchronously above.
}

module.exports = { TsJsParserServer, scan, symbolsFromSource };
