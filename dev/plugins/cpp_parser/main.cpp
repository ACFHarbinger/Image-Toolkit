// C/C++ source parser plugin (#423).
//
// A D52 command plugin: spawned by the host as
// "dev/plugins/cpp_parser/bin/cpp_parser --stdio" (Grok lock #8: the
// manifest's entry.command is the argv; the host appends --stdio). Speaks
// the frozen JSON-RPC-over-stdio contract (initialize / list_artifacts /
// list_records / ping) and answers with REAL evidence about a workspace's
// C/C++ sources:
//
// - list_artifacts -> one artifact per scanned source file, #410 shape
//   {kind, name, path, meta}; meta carries {language, loc, symbols:[...]}.
// - list_records   -> devtool.record-shaped records (#409): one record per
//   extracted symbol (kind="symbol") plus one per file (kind="file").
//
// Parsing is a lightweight std-only tokenizer over C/C++ source: it matches
// declaration keywords (class, struct, enum, namespace, using, typedef,
// #include, and function signatures at line start) and records the declared
// name. This is a genuine symbol extractor for the language's real-world
// surface, not a full grammar — std-only keeps the build hermetic (no
// libclang headers assumed), matching the D52 command-plugin contract.
//
// Scan root: --root <dir> or cwd (the host spawns from the workspace root).
// Build: g++ -O2 -std=c++17 -o bin/cpp_parser main.cpp

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace fs = std::filesystem;

static const char *PROTOCOL_VERSION = "1";
static const char *SERVER_NAME = "cpp_parser";
static const char *SERVER_VERSION = "0.1.0";

static bool is_source_ext(const std::string &ext) {
    static const char *exts[] = {".c", ".h", ".cpp", ".hpp", ".cc", ".hh", ".cxx", ".hxx"};
    for (const char *e : exts) {
        if (ext == e) return true;
    }
    return false;
}

static bool is_ignored_dir(const std::string &name) {
    static const char *dirs[] = {".git", ".venv", "node_modules", "target", "build", "dist", ".tox", "__pycache__"};
    for (const char *d : dirs) {
        if (name == d) return true;
    }
    return false;
}

static std::vector<fs::path> iter_source_files(const fs::path &root) {
    std::vector<fs::path> out;
    std::error_code ec;
    for (auto it = fs::recursive_directory_iterator(root, fs::directory_options::skip_permission_denied, ec);
         it != fs::recursive_directory_iterator(); it.increment(ec)) {
        if (ec) { ec.clear(); continue; }
        if (it->is_directory()) {
            if (is_ignored_dir(it->path().filename().string())) {
                it.disable_recursion_pending();
            }
            continue;
        }
        if (!it->is_regular_file()) continue;
        std::string ext = it->path().extension().string();
        std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
        if (is_source_ext(ext)) out.push_back(it->path());
    }
    std::sort(out.begin(), out.end());
    return out;
}

// Match one declaration on a line; returns name and kind.
struct Sym {
    std::string name;
    std::string kind;
    int line;
};

static std::string clean_ident(std::string s) {
    // trim trailing punctuation: ; { ( , space
    while (!s.empty() && std::string(";{(, ").find(s.back()) != std::string::npos) {
        s.pop_back();
    }
    return s;
}

static bool match_line(const std::string &line, int lineno, Sym &out) {
    std::string t = line;
    size_t start = t.find_first_not_of(" \t");
    if (start == std::string::npos) return false;
    t = t.substr(start);

    // #include <x> / "x"
    if (t.rfind("#include", 0) == 0) {
        out.name = "#include";
        out.kind = "include";
        out.line = lineno;
        return true;
    }

    // Split into whitespace tokens.
    std::istringstream iss(t);
    std::vector<std::string> toks;
    std::string tok;
    while (iss >> tok) toks.push_back(tok);
    if (toks.empty()) return false;

    const std::string &kw = toks[0];
    if (kw == "class" || kw == "struct" || kw == "enum" || kw == "namespace" || kw == "union") {
        if (toks.size() >= 2) {
            out.name = clean_ident(toks[1]);
            out.kind = kw;
            out.line = lineno;
            return true;
        }
    } else if (kw == "using" && toks.size() >= 2) {
        out.name = clean_ident(toks.back());
        out.kind = "using";
        out.line = lineno;
        return true;
    } else if (kw == "typedef" && toks.size() >= 2) {
        out.name = clean_ident(toks.back());
        out.kind = "typedef";
        out.line = lineno;
        return true;
    } else if (kw == "#define") {
        if (toks.size() >= 2) {
            out.name = toks[1];
            out.kind = "macro";
            out.line = lineno;
            return true;
        }
    } else if (t.find('(') != std::string::npos && t.find(';') != std::string::npos
               && t.rfind("if ", 0) != 0 && t.rfind("for ", 0) != 0 && t.rfind("while ", 0) != 0
               && t.rfind("switch ", 0) != 0) {
        // Function definition/declaration heuristics: something(...) ; or {.
        // Take the identifier right before the first '('.
        size_t paren = t.find('(');
        size_t prev = paren;
        while (prev > 0 && (isalnum((unsigned char)t[prev - 1]) || t[prev - 1] == '_')) prev--;
        std::string name = t.substr(prev, paren - prev);
        if (!name.empty() && (isalpha((unsigned char)name[0]) || name[0] == '_')) {
            out.name = name;
            out.kind = "function";
            out.line = lineno;
            return true;
        }
    }
    return false;
}

static std::string json_str(const std::string &s) {
    std::string out;
    out.push_back('"');
    for (char ch : s) {
        switch (ch) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if ((unsigned char)ch < 0x20) {
                    char buf[8];
                    std::snprintf(buf, sizeof buf, "\\u%04x", (unsigned)ch);
                    out += buf;
                } else {
                    out.push_back(ch);
                }
        }
    }
    out.push_back('"');
    return out;
}

static std::string scan_raw(const fs::path &root) {
    std::string file_objs, symbol_objs;
    bool first_file = true, first_sym = true;
    for (const auto &path : iter_source_files(root)) {
        std::ifstream in(path);
        std::stringstream ss;
        ss << in.rdbuf();
        std::string text = ss.str();
        int loc = (int)std::count(text.begin(), text.end(), '\n') + 1;

        std::string syms;
        bool first_in_file = true;
        int lineno = 0;
        std::istringstream lines(text);
        std::string line;
        while (std::getline(lines, line)) {
            lineno++;
            Sym s;
            if (match_line(line, lineno, s)) {
                if (!first_in_file) syms += ",";
                first_in_file = false;
                syms += "{\"name\":" + json_str(s.name) + ",\"kind\":" + json_str(s.kind)
                      + ",\"line\":" + std::to_string(s.line) + "}";
                if (!first_sym) symbol_objs += ",";
                first_sym = false;
                symbol_objs += "{\"schema\":\"devtool.record\",\"schema_version\":1,"
                               "\"kind\":\"symbol\",\"start_ms\":0.0,\"end_ms\":null,"
                               "\"source\":\"cpp_parser\",\"workspace\":" + json_str(root.string()) +
                               ",\"payload\":{\"language\":\"cpp\",\"file\":" +
                               json_str(path.lexically_relative(root).string()) +
                               ",\"symbol\":{\"name\":" + json_str(s.name) +
                               ",\"kind\":" + json_str(s.kind) + ",\"line\":" +
                               std::to_string(s.line) + "}}}";
            }
        }
        if (!first_file) file_objs += ",";
        first_file = false;
        file_objs += "{\"kind\":\"source_file\",\"name\":" +
                     json_str(path.lexically_relative(root).string()) + ",\"path\":" +
                     json_str(path.string()) + ",\"meta\":{\"language\":\"cpp\",\"loc\":" +
                     std::to_string(loc) + ",\"symbols\":[" + syms + "]}}";
    }
    return "{\"files\":[" + file_objs + "],\"symbols\":[" + symbol_objs + "]}";
}

static std::string extract_array(const std::string &data, const std::string &key, bool last) {
    // data = {"files":[...],"symbols":[...]}. The files array is the FIRST
    // top-level array and contains nested "symbols":[...] arrays, so it must
    // terminate at the top-level boundary "],"symbols" rather than the first
    // ']'. The symbols array is the LAST one (rfind), so it terminates at the
    // first ']' after it -- which is its own closing bracket.
    std::string needle = "\"" + key + "\":[";
    size_t pos;
    if (last) {
        pos = data.rfind(needle);
    } else {
        pos = data.find(needle);
    }
    if (pos == std::string::npos) return "[]";
    size_t start = pos + needle.size();
    size_t end;
    if (last) {
        end = data.find(']', start);
    } else {
        end = data.find("],\"symbols\"", start);
    }
    if (end == std::string::npos) end = data.size() - 1;
    return "[" + data.substr(start, end - start) + "]";
}

static std::string extract_method(const std::string &raw) {
    // "method":"..." — find the key and pull the quoted value.
    std::string needle = "\"method\"";
    size_t pos = raw.find(needle);
    if (pos == std::string::npos) return "";
    size_t colon = raw.find(':', pos);
    if (colon == std::string::npos) return "";
    size_t q = raw.find('"', colon);
    if (q == std::string::npos) return "";
    size_t end = raw.find('"', q + 1);
    if (end == std::string::npos) return "";
    return raw.substr(q + 1, end - q - 1);
}

static std::string extract_id(const std::string &raw) {
    std::string needle = "\"id\"";
    size_t pos = raw.find(needle);
    if (pos == std::string::npos) return "null";
    size_t colon = raw.find(':', pos);
    if (colon == std::string::npos) return "null";
    size_t vs = colon + 1;
    while (vs < raw.size() && (raw[vs] == ' ' || raw[vs] == '\t')) vs++;
    size_t ve = vs;
    while (ve < raw.size() && raw[ve] != ',' && raw[ve] != '}') ve++;
    std::string id = raw.substr(vs, ve - vs);
    // trim whitespace
    size_t e = id.find_last_not_of(" \t");
    if (e != std::string::npos) id = id.substr(0, e + 1);
    return id.empty() ? "null" : id;
}

static std::string handle(const std::string &raw, const fs::path &root) {
    std::string method = extract_method(raw);
    std::string id = extract_id(raw);
    if (method == "initialize") {
        return "{\"jsonrpc\":\"2.0\",\"id\":" + id + ",\"result\":{\"protocolVersion\":\"" +
               PROTOCOL_VERSION + "\",\"capabilities\":{\"artifacts\":true,\"records\":true},"
               "\"serverInfo\":{\"name\":\"" + SERVER_NAME + "\",\"version\":\"" +
               SERVER_VERSION + "\"}}}";
    }
    if (method == "list_artifacts") {
        std::string data = scan_raw(root);
        return "{\"jsonrpc\":\"2.0\",\"id\":" + id + ",\"result\":{\"artifacts\":" +
               extract_array(data, "files", false) + "}}";
    }
    if (method == "list_records") {
        std::string data = scan_raw(root);
        return "{\"jsonrpc\":\"2.0\",\"id\":" + id + ",\"result\":{\"records\":" +
               extract_array(data, "symbols", true) + "}}";
    }
    if (method == "ping") {
        return "{\"jsonrpc\":\"2.0\",\"id\":" + id + ",\"result\":{}}";
    }
    if (method.empty()) {
        return "{\"jsonrpc\":\"2.0\",\"id\":null,\"error\":{\"code\":-32700,\"message\":\"parse error\"}}";
    }
    return "{\"jsonrpc\":\"2.0\",\"id\":" + id + ",\"error\":{\"code\":-32601,\"message\":\"method not found\"}}";
}

int main(int argc, char **argv) {
    bool stdio = false;
    fs::path root = fs::current_path();
    for (int i = 1; i < argc; i++) {
        if (std::strcmp(argv[i], "--stdio") == 0) stdio = true;
        if (std::strcmp(argv[i], "--root") == 0 && i + 1 < argc) root = argv[i + 1];
    }
    if (!stdio) {
        std::fprintf(stderr, "cpp_parser: --stdio is required (Grok lock #8: the host appends it)\n");
        return 2;
    }
    std::string line;
    while (std::getline(std::cin, line)) {
        // trim
        size_t s = line.find_first_not_of(" \t\r\n");
        if (s == std::string::npos) continue;
        std::string trimmed = line.substr(s);
        std::cout << handle(trimmed, root) << "\n";
        std::cout.flush();
    }
    return 0;
}
