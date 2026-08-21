// Rust source parser plugin (#423).
//
// A D52 command plugin: spawned by the host as
// "dev/plugins/rust_parser/bin/rust_parser --stdio" (Grok lock #8: the
// manifest's entry.command is the argv; the host appends --stdio). Speaks
// the frozen JSON-RPC-over-stdio contract (initialize / list_artifacts /
// list_records / ping) and answers with REAL evidence about a workspace's
// Rust sources:
//
// - list_artifacts -> one artifact per scanned .rs file, #410 shape
//   {kind, name, path, meta}; meta carries {language, loc, symbols:[...]}.
// - list_records   -> devtool.record-shaped records (#409): one record per
//   extracted symbol (kind="symbol") plus one per file (kind="file").
//
// Parsing is a lightweight, std-only tokenizer over Rust source: it matches
// top-level item keywords (fn, struct, enum, trait, impl, mod, use, const,
// static, type) at line start (or after leading whitespace) and records the
// declared name. This is a genuine symbol/definition extractor, not a full
// Rust grammar - it needs no external crates (cargo network access is not
// assumed), which keeps the build hermetic for the D52 command contract.
//
// Scan root: --root <dir> or cwd (the host spawns from the workspace root).
// Build: cargo build --release --offline  (std only).

use std::collections::HashSet;
use std::env;
use std::fs;
use std::io::{self, BufRead, Write};
use std::path::{Path, PathBuf};

const PROTOCOL_VERSION: &str = "1";
const SERVER_NAME: &str = "rust_parser";
const SERVER_VERSION: &str = "0.1.0";

fn ignored_dirs() -> HashSet<&'static str> {
    [".git", ".venv", "node_modules", "target", "build", "dist", ".tox", "__pycache__"]
        .iter().copied().collect()
}

fn iter_rust_files(root: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    let ignored = ignored_dirs();
    fn walk(dir: &Path, ignored: &HashSet<&'static str>, out: &mut Vec<PathBuf>) {
        if let Ok(entries) = fs::read_dir(dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.is_dir() {
                    if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                        if !ignored.contains(name) {
                            walk(&path, ignored, out);
                        }
                    }
                } else if path.extension().and_then(|e| e.to_str()) == Some("rs") {
                    out.push(path);
                }
            }
        }
    }
    walk(root, &ignored, &mut out);
    out.sort();
    out
}

/// Clean a symbol name token: strip trailing punctuation and generics
/// ({, ;, (, <T>).
fn clean_name(s: &str) -> String {
    let mut seg = s.to_string();
    seg.retain(|c| !matches!(c, '{' | ';' | ',' | '(' | ')' | '<' | '>'));
    seg
}

/// Match a Rust item keyword and return (keyword, name, line). Skips leading
/// visibility/attribute modifiers (pub, pub(crate), async, unsafe, etc.).
fn match_item(line: &str, line_no: usize) -> Option<(String, String, usize)> {
    let trimmed = line.trim_start();
    let mut words = trimmed.split_whitespace();
    let mut kw = words.next()?.to_string();
    while matches!(
        kw.as_str(),
        "pub" | "pub(crate)" | "pub(super)" | "async" | "unsafe" | "extern" | "default"
    ) {
        kw = words.next()?.to_string();
    }
    let name: String = match kw.as_str() {
        "impl" => {
            // impl Trait for Type / impl Type - record the type name that
            // follows 'for' if present, else the first ident.
            let rest: Vec<&str> = words.collect();
            rest.iter()
                .position(|w| *w == "for")
                .and_then(|i| rest.get(i + 1))
                .copied()
                .map(clean_name)
                .or_else(|| rest.first().copied().map(clean_name))
                .unwrap_or_else(|| "<impl>".to_string())
        }
        "use" => {
            // use a::b::{c, d}; - record the last path segment, cleaned of
            // trailing punctuation ({, ;, ,, ().
            let rest: Vec<&str> = words.collect();
            rest.first()
                .map(|s| {
                    let mut seg = s
                        .split("::")
                        .filter(|p| !p.is_empty())
                        .last()
                        .unwrap_or("")
                        .to_string();
                    seg.retain(|c| !matches!(c, '{' | ';' | ',' | '(' | ')'));
                    seg
                })
                .unwrap_or_default()
        }
        "fn" | "struct" | "enum" | "trait" | "mod" | "const" | "static" | "type" => words
            .next()
            .map(clean_name)
            .unwrap_or_default(),
        _ => return None,
    };
    Some((kw, name, line_no))
}

fn scan_raw(root: &Path) -> String {
    let files = iter_rust_files(root);
    let mut file_objs: Vec<String> = Vec::new();
    let mut symbol_objs: Vec<String> = Vec::new();
    for path in &files {
        let text = match fs::read_to_string(path) {
            Ok(t) => t,
            Err(_) => continue,
        };
        let loc = text.lines().count();
        let mut syms: Vec<String> = Vec::new();
        for (idx, line) in text.lines().enumerate() {
            if let Some((kw, name, _line_no)) = match_item(line, idx + 1) {
                syms.push(format!(
                    "{{\"name\":{},\"kind\":{},\"line\":{}}}",
                    json_str(&name),
                    json_str(&kw),
                    idx + 1
                ));
            }
        }
        let rel = path.strip_prefix(root).unwrap_or(path).to_string_lossy().to_string();
        file_objs.push(format!(
            "{{\"kind\":\"source_file\",\"name\":{},\"path\":{},\"meta\":{{\"language\":\"rust\",\"loc\":{},\"symbols\":[{}]}}}}",
            json_str(&rel),
            json_str(&path.to_string_lossy()),
            loc,
            syms.join(",")
        ));
        for sym in &syms {
            symbol_objs.push(format!(
                "{{\"schema\":\"devtool.record\",\"schema_version\":1,\"kind\":\"symbol\",\"start_ms\":0.0,\"end_ms\":null,\"source\":\"rust_parser\",\"workspace\":{},\"payload\":{{\"language\":\"rust\",\"file\":{},\"symbol\":{}}}}}",
                json_str(&root.to_string_lossy()),
                json_str(&rel),
                sym
            ));
        }
    }
    format!("{{\"files\":[{}],\"symbols\":[{}]}}", file_objs.join(","), symbol_objs.join(","))
}

fn json_str(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('"');
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

fn extract_string_member(raw: &str, key: &str) -> Option<String> {
    let needle = format!("\"{}\"", key);
    let mut search_from = 0;
    while let Some(pos) = raw[search_from..].find(&needle) {
        let key_start = search_from + pos;
        let after_key = key_start + needle.len();
        let rest = &raw[after_key..];
        let trimmed = rest.trim_start();
        if trimmed.starts_with(':') {
            let value = trimmed[1..].trim_start();
            if value.starts_with('"') {
                let end = value[1..].find('"')?;
                return Some(value[1..1 + end].to_string());
            }
            return None;
        }
        search_from = after_key;
    }
    None
}

fn extract_method(raw: &str) -> Option<String> {
    extract_string_member(raw, "method")
}

fn extract_id(raw: &str) -> Option<String> {
    // "id" may be a string ("x"), a number (1), or null. Scan for the key,
    // skip the colon, and copy the raw token up to the next comma/brace.
    let key = "\"id\"";
    let mut search_from = 0;
    while let Some(pos) = raw[search_from..].find(key) {
        let key_start = search_from + pos;
        let after_key = key_start + key.len();
        let rest = &raw[after_key..];
        let trimmed = rest.trim_start();
        if !trimmed.starts_with(':') {
            search_from = after_key;
            continue;
        }
        let value = trimmed[1..].trim_start();
        let value_len = value
            .find(|c: char| c == ',' || c == '}' || c.is_whitespace())
            .unwrap_or(value.len());
        let value_end = after_key + (rest.len() - trimmed.len()) + 1 + (trimmed[1..].len() - value.len()) + value_len;
        let value_start = value_end - value_len;
        if value_len > 0 {
            return Some(raw[value_start..value_end].to_string());
        }
        search_from = after_key;
    }
    None
}

fn extract_files(data: &str) -> String {
    // data = {"files":[...],"symbols":[...]}
    let files_start = match data.find("\"files\":[") {
        Some(i) => i + "\"files\":[".len(),
        None => return "[]".to_string(),
    };
    let rest = &data[files_start..];
    let end = match rest.find("],\"symbols\"") {
        Some(i) => i,
        None => rest.len().saturating_sub(1),
    };
    format!("[{}]", &rest[..end])
}

fn extract_symbols(data: &str) -> String {
    // The top-level "symbols":[ ... ] array is the LAST one (file metas embed
    // their own "symbols":[ ... ] arrays earlier), so scan from the end.
    let syms_start = match data.rfind("\"symbols\":[") {
        Some(i) => i + "\"symbols\":[".len(),
        None => return "[]".to_string(),
    };
    let rest = &data[syms_start..];
    let end = match rest.find(']') {
        Some(i) => i,
        None => rest.len().saturating_sub(1),
    };
    format!("[{}]", &rest[..end])
}

fn handle(raw: &str, root: &Path) -> Option<String> {
    let method = extract_method(raw);
    let id = extract_id(raw);
    match method.as_deref() {
        Some("initialize") => Some(format!(
            "{{\"jsonrpc\":\"2.0\",\"id\":{},\"result\":{{\"protocolVersion\":\"{}\",\"capabilities\":{{\"artifacts\":true,\"records\":true}},\"serverInfo\":{{\"name\":\"{}\",\"version\":\"{}\"}}}}}}",
            id.unwrap_or_else(|| "null".to_string()),
            PROTOCOL_VERSION,
            SERVER_NAME,
            SERVER_VERSION
        )),
        Some("list_artifacts") => {
            let data = scan_raw(root);
            Some(format!(
                "{{\"jsonrpc\":\"2.0\",\"id\":{},\"result\":{{\"artifacts\":{}}}}}",
                id.unwrap_or_else(|| "null".to_string()),
                extract_files(&data)
            ))
        }
        Some("list_records") => {
            let data = scan_raw(root);
            Some(format!(
                "{{\"jsonrpc\":\"2.0\",\"id\":{},\"result\":{{\"records\":{}}}}}",
                id.unwrap_or_else(|| "null".to_string()),
                extract_symbols(&data)
            ))
        }
        Some("ping") => Some(format!(
            "{{\"jsonrpc\":\"2.0\",\"id\":{},\"result\":{{}}}}",
            id.unwrap_or_else(|| "null".to_string())
        )),
        Some(m) => Some(format!(
            "{{\"jsonrpc\":\"2.0\",\"id\":{},\"error\":{{\"code\":-32601,\"message\":\"method not found: {}\"}}}}",
            id.unwrap_or_else(|| "null".to_string()),
            json_str(m)
        )),
        None => {
            if raw.trim().is_empty() {
                None
            } else {
                Some(format!(
                    "{{\"jsonrpc\":\"2.0\",\"id\":null,\"error\":{{\"code\":-32700,\"message\":\"parse error\"}}}}"
                ))
            }
        }
    }
}

fn serve_stdio(root: &Path) -> io::Result<()> {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut out = stdout.lock();
    for line in stdin.lock().lines() {
        let line = line?;
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        if let Some(response) = handle(trimmed, root) {
            writeln!(out, "{}", response)?;
        }
    }
    Ok(())
}

fn main() -> io::Result<()> {
    let argv: Vec<String> = env::args().collect();
    if !argv.iter().any(|a| a == "--stdio") {
        eprintln!("rust_parser: --stdio is required (Grok lock #8: the host appends it)");
        std::process::exit(2);
    }
    let root = match argv.iter().position(|a| a == "--root") {
        Some(i) if i + 1 < argv.len() => PathBuf::from(&argv[i + 1]),
        _ => env::current_dir()?,
    };
    serve_stdio(&root)
}
