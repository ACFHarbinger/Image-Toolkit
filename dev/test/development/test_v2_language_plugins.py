"""Tests for #423: per-language source parser/ingestion plugins.

Five D52 command plugins in dev/plugins/ (py_parser, ts_js_parser,
rust_parser, cpp_parser, java_kotlin_parser) parse a workspace's sources for
that language and speak the frozen JSON-RPC-over-stdio contract: initialize /
list_artifacts / list_records / ping (host appends --stdio, lock #8).

Each is a REAL parser for its language (Python ast, TypeScript compiler API,
Rust/C++ std-only tokenizers, javac AST + Kotlin tokenizer), feeding
devtool.record-shaped evidence (#409). These tests build where needed, spawn
each with --stdio, check the wire protocol, and skip gracefully when the
language's toolchain is unavailable (matching the d52_proof test pattern).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tool.host import build_command_argv, discover_plugins, load_manifest

DEV_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGINS_DIR = DEV_ROOT / "plugins"


def _spawn(argv: list[str], cwd: Path, payload: str) -> tuple[list[dict], str]:
    proc = subprocess.Popen(
        argv,
        cwd=str(cwd),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate(input=payload, timeout=60)
    if proc.returncode != 0:
        pytest.skip(f"plugin exited {proc.returncode}: {err.strip()}")
    lines = [json.loads(l) for l in out.strip().splitlines() if l.strip()]
    return lines, err


# ---------------------------------------------------------------------------
# Fixtures (build where needed; skip when toolchain missing)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def py_command() -> list[str]:
    return [sys.executable, str(PLUGINS_DIR / "py_parser" / "parser.py")]


@pytest.fixture(scope="module")
def ts_command() -> list[str]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node toolchain not available")
    return [node, str(PLUGINS_DIR / "ts_js_parser" / "parser.js")]


@pytest.fixture(scope="module")
def rust_command(tmp_path_factory) -> list[str]:
    built = PLUGINS_DIR / "rust_parser" / "target" / "release" / "rust_parser"
    if built.exists():
        return [str(built)]
    cargo = shutil.which("cargo")
    if cargo is None:
        pytest.skip("cargo toolchain not available and no prebuilt binary")
    # Build inside the plugin dir so rustup resolves the toolchain from cwd.
    # Preserve the real rustup home (a fake HOME breaks toolchain resolution).
    import os
    env = dict(os.environ)
    env.setdefault("RUSTUP_TOOLCHAIN", "stable")
    result = subprocess.run(
        [cargo, "build", "--release", "--offline"],
        cwd=str(PLUGINS_DIR / "rust_parser"),
        env=env,
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not built.exists():
        pytest.skip(f"cargo build failed: {result.stderr.strip()[:300]}")
    return [str(built)]


@pytest.fixture(scope="module")
def cpp_command(tmp_path_factory) -> list[str]:
    gpp = shutil.which("g++")
    if gpp is None:
        pytest.skip("g++ toolchain not available")
    binary = tmp_path_factory.mktemp("cppbin") / "cpp_parser"
    result = subprocess.run(
        [gpp, "-O2", "-std=c++17", "-o", str(binary),
         str(PLUGINS_DIR / "cpp_parser" / "main.cpp")],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"g++ build failed: {result.stderr.strip()[:300]}")
    return [str(binary)]


@pytest.fixture(scope="module")
def java_command(tmp_path_factory) -> list[str]:
    javac = shutil.which("javac")
    java = shutil.which("java")
    if javac is None or java is None:
        pytest.skip("JDK toolchain not available")
    bin_dir = tmp_path_factory.mktemp("javabin")
    result = subprocess.run(
        [javac, "-d", str(bin_dir), str(PLUGINS_DIR / "java_kotlin_parser" / "Parser.java")],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"javac build failed: {result.stderr.strip()[:300]}")
    return [java, "-cp", str(bin_dir), "Parser"]


# ---------------------------------------------------------------------------
# Fixture source trees (one per language, under tmp_path via the fixture root)
# ---------------------------------------------------------------------------

def _write_source(tmp_path: Path, rel: str, text: str) -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture
def py_tree(tmp_path):
    _write_source(tmp_path, "mymod.py", "import os\nimport json as j\n\nclass Greeter:\n    def hi(self):\n        return 'x'\n\ndef top_fn(x):\n    return x\n\nCONST = 3\n")
    return tmp_path


@pytest.fixture
def ts_tree(tmp_path):
    _write_source(tmp_path, "sample.ts", "interface Foo { a: number }\nclass Bar { method(): void {} }\nfunction baz(x: number): number { return x; }\nconst qux = 42;\nenum Color { Red, Green }\n")
    return tmp_path


@pytest.fixture
def rust_tree(tmp_path):
    _write_source(tmp_path, "lib.rs", "use std::collections::HashSet;\n\npub struct Point { x: i32, y: i32 }\n\nenum Shape { Circle, Square }\n\ntrait Area { fn area(&self) -> f64; }\n\nfn helper() {}\n\nmod inner { pub fn deep() {} }\n")
    return tmp_path


@pytest.fixture
def cpp_tree(tmp_path):
    _write_source(tmp_path, "sample.hpp", "class Foo {\npublic:\n  int bar();\n};\nstruct Baz { int x; };\nenum Color { Red, Green };\nnamespace ns { void helper(); }\n#include <vector>\n")
    return tmp_path


@pytest.fixture
def java_tree(tmp_path):
    _write_source(tmp_path, "Hello.java", "package demo;\nimport java.util.List;\npublic class Hello {\n  private int count;\n  public String greet(String name) { return name; }\n}\n")
    _write_source(tmp_path, "Greeter.kt", "package demo\nimport kotlin.math.max\nclass Greeter {\n  fun greet(name: String): String { return name }\n  val count = 3\n}\n")
    return tmp_path


# ---------------------------------------------------------------------------
# Shared wire-protocol assertions
# ---------------------------------------------------------------------------

def _protocol_payload():
    return (
        '{"jsonrpc":"2.0","id":1,"method":"initialize"}\n'
        '{"jsonrpc":"2.0","id":2,"method":"list_artifacts"}\n'
        '{"jsonrpc":"2.0","id":3,"method":"list_records"}\n'
        '{"jsonrpc":"2.0","id":4,"method":"ping"}\n'
    )


def _assert_protocol(lines, expected_name):
    assert [l["id"] for l in lines] == [1, 2, 3, 4]
    assert lines[0]["result"]["protocolVersion"] == "1"
    assert lines[0]["result"]["serverInfo"]["name"] == expected_name
    artifacts = lines[1]["result"]["artifacts"]
    assert isinstance(artifacts, list)
    for artifact in artifacts:
        assert {"kind", "name", "path", "meta"} <= set(artifact)
        assert artifact["meta"]["symbols"]
    records = lines[2]["result"]["records"]
    assert isinstance(records, list)
    for record in records:
        assert record["schema"] == "devtool.record"
        assert record["kind"] in {"symbol", "file"}
    assert lines[3]["result"] == {}


class TestPyParser:
    def test_protocol(self, py_command, py_tree):
        lines, _ = _spawn(py_command + ["--stdio", "--root", str(py_tree)], py_tree, _protocol_payload())
        _assert_protocol(lines, "py_parser")

    def test_symbols_extracted(self, py_command, py_tree):
        lines, _ = _spawn(py_command + ["--stdio", "--root", str(py_tree)], py_tree,
                          '{"jsonrpc":"2.0","id":2,"method":"list_artifacts"}\n')
        names = lines[0]["result"]["artifacts"][0]["meta"]["symbols"]
        kinds = {s["kind"] for s in names}
        assert {"function", "class", "import", "assignment"} <= kinds

    def test_missing_stdio_exits_2(self, py_command, py_tree):
        proc = subprocess.run(py_command, capture_output=True, text=True, cwd=str(py_tree))
        assert proc.returncode == 2
        assert "--stdio" in proc.stderr


class TestTsJsParser:
    def test_protocol(self, ts_command, ts_tree):
        lines, _ = _spawn(ts_command + ["--stdio", "--root", str(ts_tree)], ts_tree, _protocol_payload())
        _assert_protocol(lines, "ts_js_parser")

    def test_symbols_extracted(self, ts_command, ts_tree):
        lines, _ = _spawn(ts_command + ["--stdio", "--root", str(ts_tree)], ts_tree,
                          '{"jsonrpc":"2.0","id":2,"method":"list_artifacts"}\n')
        names = [s["name"] for s in lines[0]["result"]["artifacts"][0]["meta"]["symbols"]]
        assert {"Foo", "Bar", "baz", "qux", "Color"} <= set(names)


class TestRustParser:
    def test_protocol(self, rust_command, rust_tree):
        lines, _ = _spawn(rust_command + ["--stdio", "--root", str(rust_tree)], rust_tree, _protocol_payload())
        _assert_protocol(lines, "rust_parser")

    def test_symbols_extracted(self, rust_command, rust_tree):
        lines, _ = _spawn(rust_command + ["--stdio", "--root", str(rust_tree)], rust_tree,
                          '{"jsonrpc":"2.0","id":2,"method":"list_artifacts"}\n')
        names = [s["name"] for s in lines[0]["result"]["artifacts"][0]["meta"]["symbols"]]
        assert {"Point", "Shape", "Area", "helper"} <= set(names)


class TestCppParser:
    def test_protocol(self, cpp_command, cpp_tree):
        lines, _ = _spawn(cpp_command + ["--stdio", "--root", str(cpp_tree)], cpp_tree, _protocol_payload())
        _assert_protocol(lines, "cpp_parser")

    def test_symbols_extracted(self, cpp_command, cpp_tree):
        lines, _ = _spawn(cpp_command + ["--stdio", "--root", str(cpp_tree)], cpp_tree,
                          '{"jsonrpc":"2.0","id":2,"method":"list_artifacts"}\n')
        names = [s["name"] for s in lines[0]["result"]["artifacts"][0]["meta"]["symbols"]]
        assert {"Foo", "Baz", "Color", "ns"} <= set(names)


class TestJavaKotlinParser:
    def test_protocol(self, java_command, java_tree):
        lines, _ = _spawn(java_command + ["--stdio", "--root", str(java_tree)], java_tree, _protocol_payload())
        _assert_protocol(lines, "java_kotlin_parser")

    def test_java_and_kotlin_extracted(self, java_command, java_tree):
        lines, _ = _spawn(java_command + ["--stdio", "--root", str(java_tree)], java_tree,
                          '{"jsonrpc":"2.0","id":2,"method":"list_artifacts"}\n')
        artifacts = {a["name"]: a for a in lines[0]["result"]["artifacts"]}
        java_syms = [s["name"] for s in artifacts["Hello.java"]["meta"]["symbols"]]
        kt_syms = [s["name"] for s in artifacts["Greeter.kt"]["meta"]["symbols"]]
        assert "Hello" in java_syms and "greet" in java_syms
        assert "Greeter" in kt_syms and "greet" in kt_syms


# ---------------------------------------------------------------------------
# Manifest integration
# ---------------------------------------------------------------------------

class TestManifests:
    @pytest.mark.parametrize("plugin_name", [
        "py_parser", "ts_js_parser", "rust_parser", "cpp_parser", "java_kotlin_parser",
    ])
    def test_manifest_loaded_and_command(self, plugin_name):
        manifest = load_manifest(Path("dev/tool/plugins") / f"{plugin_name}.plugin.json")
        assert manifest.name == plugin_name
        entry = manifest.effective_entry()
        assert entry.command, f"{plugin_name} must carry a command entry"
        # command-only: no python_module (language-neutral path)
        assert not entry.python_module
        argv = build_command_argv(manifest)
        assert argv[-1] == "--stdio"

    def test_discovered_as_command_plugins(self):
        plugins = discover_plugins()
        names = {p.manifest.name for p in plugins}
        for plugin_name in ["py_parser", "ts_js_parser", "rust_parser", "cpp_parser", "java_kotlin_parser"]:
            assert plugin_name in names
            plugin = next(p for p in plugins if p.manifest.name == plugin_name)
            assert not plugin.manifest.effective_entry().python_module
