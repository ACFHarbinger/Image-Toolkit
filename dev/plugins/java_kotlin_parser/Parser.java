// Java/Kotlin source parser plugin (#423).
//
// A D52 command plugin: spawned by the host as
// "java -cp dev/plugins/java_kotlin_parser/bin Parser --stdio"
// (Grok lock #8: the manifest's entry.command is the argv; the host appends
// --stdio). Speaks the frozen JSON-RPC-over-stdio contract (initialize /
// list_artifacts / list_records / ping) and answers with REAL evidence about
// a workspace's Java/Kotlin sources:
//
// - list_artifacts -> one artifact per scanned source file, #410 shape
//   {kind, name, path, meta}; meta carries {language, loc, symbols:[...]}.
// - list_records   -> devtool.record-shaped records (#409): one record per
//   extracted symbol (kind="symbol") plus one per file (kind="file").
//
// Java is parsed with the real javac AST (com.sun.source / JavacTask) --
// the compiler's own parser, available in any JDK. Kotlin uses a lightweight
// tokenizer (kotlinc ships no public tree API in this shape); both extract
// classes/methods/fields/imports plus per-file metrics.
//
// Scan root: --root <dir> or cwd (the host spawns from the workspace root).
// Build: javac -d bin Parser.java   (JDK 11+; com.sun.source is exported
// from the jdk.compiler module, no module path needed for a classpath app).

import com.sun.source.tree.ClassTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.ImportTree;
import com.sun.source.tree.MethodTree;
import com.sun.source.tree.Tree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.TreeScanner;

import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;
import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public class Parser {

    static final String PROTOCOL_VERSION = "1";
    static final String SERVER_NAME = "java_kotlin_parser";
    static final String SERVER_VERSION = "0.1.0";

    static final Set<String> IGNORED_DIRS = new HashSet<>(Arrays.asList(
            ".git", ".venv", "node_modules", "target", "build", "dist", ".tox", "__pycache__"));

    // ---------------------------------------------------------------- scan

    static List<Path> iterSourceFiles(Path root) throws IOException {
        List<Path> out = new ArrayList<>();
        Files.walkFileTree(root, new SimpleFileVisitor<Path>() {
            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) {
                if (!dir.equals(root) && IGNORED_DIRS.contains(dir.getFileName().toString())) {
                    return FileVisitResult.SKIP_SUBTREE;
                }
                return FileVisitResult.CONTINUE;
            }
            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) {
                String name = file.getFileName().toString();
                if (name.endsWith(".java") || name.endsWith(".kt") || name.endsWith(".kts")) {
                    out.add(file);
                }
                return FileVisitResult.CONTINUE;
            }
        });
        out.sort(Path::compareTo);
        return out;
    }

    // symbol = {name, kind, line}
    static class Sym {
        String name;
        String kind;
        int line;
        Sym(String name, String kind, int line) { this.name = name; this.kind = kind; this.line = line; }
    }

    static List<Sym> symbolsFromJava(String text, Path path) {
        List<Sym> syms = new ArrayList<>();
        try {
            JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
            if (compiler == null) return syms;
            StandardJavaFileManager fm = compiler.getStandardFileManager(null, null, StandardCharsets.UTF_8);
            JavaFileObject src = new javax.tools.SimpleJavaFileObject(path.toUri(), JavaFileObject.Kind.SOURCE) {
                @Override
                public CharSequence getCharContent(boolean ignore) { return text; }
            };
            Iterable<? extends JavaFileObject> units = List.of(src);
            JavacTask task = (JavacTask) compiler.getTask(null, fm, null, List.of("-proc:none"), null, units);
            com.sun.source.util.Trees trees = com.sun.source.util.Trees.instance(task);
            for (CompilationUnitTree unit : task.parse()) {
                com.sun.source.util.SourcePositions positions = trees.getSourcePositions();
                new TreeScanner<Void, Void>() {
                    private long lineOf(Tree node) {
                        long pos = positions.getStartPosition(unit, node);
                        return pos >= 0 ? unit.getLineMap().getLineNumber(pos) : 0;
                    }
                    @Override
                    public Void visitClass(ClassTree node, Void unused) {
                        if (node.getSimpleName() != null && node.getSimpleName().length() > 0) {
                            syms.add(new Sym(node.getSimpleName().toString(), "class", (int) lineOf(node)));
                        }
                        return super.visitClass(node, null);
                    }
                    @Override
                    public Void visitMethod(MethodTree node, Void unused) {
                        if (node.getName() != null && node.getName().length() > 0) {
                            syms.add(new Sym(node.getName().toString(), "method", (int) lineOf(node)));
                        }
                        return super.visitMethod(node, null);
                    }
                    @Override
                    public Void visitImport(ImportTree node, Void unused) {
                        syms.add(new Sym(node.getQualifiedIdentifier().toString(), "import", (int) lineOf(node)));
                        return super.visitImport(node, null);
                    }
                }.scan(unit, null);
            }
            fm.close();
        } catch (Exception e) {
            // javac AST failed (e.g. syntax error) — fall through with what we have
        }
        return syms;
    }

    static List<Sym> symbolsFromKotlin(String text) {
        List<Sym> syms = new ArrayList<>();
        int line = 0;
        for (String rawLine : text.split("\\n")) {
            line++;
            String l = rawLine.trim();
            if (l.startsWith("import ")) {
                syms.add(new Sym(cleanIdent(l.substring("import ".length())), "import", line));
            } else if (l.matches("(public |private |internal |protected |open |abstract |sealed |data |enum )*(class|interface|object|fun|val|var|typealias|enum class) .*")) {
                String kw = l.split("\\s+")[l.startsWith("enum") ? 1 : 0];
                // find the identifier token
                String[] toks = l.split("\\s+");
                int nameIdx = -1;
                for (int i = 0; i < toks.length; i++) {
                    if (toks[i].equals("class") || toks[i].equals("interface") || toks[i].equals("object")
                            || toks[i].equals("fun") || toks[i].equals("val") || toks[i].equals("var")
                            || toks[i].equals("typealias") || toks[i].equals("enum")) {
                        if (i + 1 < toks.length) { nameIdx = i + 1; break; }
                    }
                }
                if (nameIdx >= 0) {
                    String name = cleanIdent(toks[nameIdx]);
                    if (l.contains("fun ")) kw = "function";
                    else if (l.contains("val ") || l.contains("var ")) kw = "property";
                    else kw = "declaration";
                    syms.add(new Sym(name, kw, line));
                }
            }
        }
        return syms;
    }

    static String cleanIdent(String s) {
        StringBuilder sb = new StringBuilder();
        for (char c : s.toCharArray()) {
            if (Character.isLetterOrDigit(c) || c == '_' || c == '.') sb.append(c);
            else break;
        }
        return sb.toString();
    }

    static class FileInfo {
        Path path;
        String rel;
        int loc;
        List<Sym> syms;
    }

    static List<FileInfo> scan(Path root) throws IOException {
        List<FileInfo> files = new ArrayList<>();
        for (Path p : iterSourceFiles(root)) {
            String text;
            try {
                text = Files.readString(p, StandardCharsets.UTF_8);
            } catch (IOException e) {
                continue;
            }
            List<Sym> syms = p.getFileName().toString().endsWith(".java")
                    ? symbolsFromJava(text, p)
                    : symbolsFromKotlin(text);
            FileInfo fi = new FileInfo();
            fi.path = p;
            fi.rel = root.relativize(p).toString();
            fi.loc = text.split("\\n", -1).length;
            fi.syms = syms;
            files.add(fi);
        }
        return files;
    }

    // ---------------------------------------------------------------- JSON

    static String jsonStr(String s) {
        StringBuilder out = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            switch (c) {
                case '"': out.append('"'); break;
                case '\\': out.append("\\\\"); break;
                case '\n': out.append("\\n"); break;
                case '\r': out.append("\\r"); break;
                case '\t': out.append("\\t"); break;
                default:
                    if (c < 0x20) out.append(String.format("\\u%04x", (int) c));
                    else out.append(c);
            }
        }
        out.append('"');
        return out.toString();
    }

    static String symJson(Sym s) {
        return "{\"name\":" + jsonStr(s.name) + ",\"kind\":" + jsonStr(s.kind)
                + ",\"line\":" + s.line + "}";
    }

    static String recordJson(Sym s, String rel, Path root) {
        return "{\"schema\":\"devtool.record\",\"schema_version\":1,\"kind\":\"symbol\","
                + "\"start_ms\":0.0,\"end_ms\":null,\"source\":\"java_kotlin_parser\","
                + "\"workspace\":" + jsonStr(root.toString())
                + ",\"payload\":{\"language\":\"java\",\"file\":" + jsonStr(rel)
                + ",\"symbol\":" + symJson(s) + "}}";
    }

    static String fileJson(FileInfo f) {
        StringBuilder syms = new StringBuilder();
        for (int i = 0; i < f.syms.size(); i++) {
            if (i > 0) syms.append(',');
            syms.append(symJson(f.syms.get(i)));
        }
        return "{\"kind\":\"source_file\",\"name\":" + jsonStr(f.rel)
                + ",\"path\":" + jsonStr(f.path.toString())
                + ",\"meta\":{\"language\":\"java\",\"loc\":" + f.loc
                + ",\"symbols\":[" + syms + "]}}";
    }

    static String extractMember(String raw, String key) {
        String needle = "\"" + key + "\"";
        int pos = raw.indexOf(needle);
        if (pos < 0) return "";
        int colon = raw.indexOf(':', pos);
        if (colon < 0) return "";
        int q = raw.indexOf('"', colon);
        if (q < 0) return "";
        int end = raw.indexOf('"', q + 1);
        if (end < 0) return "";
        return raw.substring(q + 1, end);
    }

    static String extractId(String raw) {
        String needle = "\"id\"";
        int pos = raw.indexOf(needle);
        if (pos < 0) return "null";
        int colon = raw.indexOf(':', pos);
        if (colon < 0) return "null";
        int vs = colon + 1;
        while (vs < raw.length() && (raw.charAt(vs) == ' ' || raw.charAt(vs) == '\t')) vs++;
        int ve = vs;
        while (ve < raw.length() && raw.charAt(ve) != ',' && raw.charAt(ve) != '}') ve++;
        String id = raw.substring(vs, ve).trim();
        return id.isEmpty() ? "null" : id;
    }

    static String handle(String raw, Path root) throws IOException {
        String method = extractMember(raw, "method");
        String id = extractId(raw);
        if (method.equals("initialize")) {
            return "{\"jsonrpc\":\"2.0\",\"id\":" + id + ",\"result\":{\"protocolVersion\":\""
                    + PROTOCOL_VERSION + "\",\"capabilities\":{\"artifacts\":true,\"records\":true},"
                    + "\"serverInfo\":{\"name\":\"" + SERVER_NAME + "\",\"version\":\""
                    + SERVER_VERSION + "\"}}}";
        }
        if (method.equals("list_artifacts")) {
            List<FileInfo> files = scan(root);
            StringBuilder out = new StringBuilder();
            for (int i = 0; i < files.size(); i++) {
                if (i > 0) out.append(',');
                out.append(fileJson(files.get(i)));
            }
            return "{\"jsonrpc\":\"2.0\",\"id\":" + id + ",\"result\":{\"artifacts\":[" + out + "]}}";
        }
        if (method.equals("list_records")) {
            List<FileInfo> files = scan(root);
            StringBuilder out = new StringBuilder();
            for (FileInfo f : files) {
                for (Sym s : f.syms) {
                    if (out.length() > 0) out.append(',');
                    out.append(recordJson(s, f.rel, root));
                }
            }
            return "{\"jsonrpc\":\"2.0\",\"id\":" + id + ",\"result\":{\"records\":[" + out + "]}}";
        }
        if (method.equals("ping")) {
            return "{\"jsonrpc\":\"2.0\",\"id\":" + id + ",\"result\":{}}";
        }
        if (method.isEmpty()) {
            return "{\"jsonrpc\":\"2.0\",\"id\":null,\"error\":{\"code\":-32700,\"message\":\"parse error\"}}";
        }
        return "{\"jsonrpc\":\"2.0\",\"id\":" + id + ",\"error\":{\"code\":-32601,\"message\":\"method not found\"}}";
    }

    public static void main(String[] args) throws IOException {
        boolean stdio = false;
        Path root = Path.of(".").toAbsolutePath();
        for (int i = 0; i < args.length; i++) {
            if (args[i].equals("--stdio")) stdio = true;
            if (args[i].equals("--root") && i + 1 < args.length) root = Path.of(args[i + 1]).toAbsolutePath();
        }
        if (!stdio) {
            System.err.println("java_kotlin_parser: --stdio is required (Grok lock #8: the host appends it)");
            System.exit(2);
        }
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        String line;
        while ((line = in.readLine()) != null) {
            String t = line.trim();
            if (t.isEmpty()) continue;
            System.out.println(handle(t, root));
            System.out.flush();
        }
    }
}
