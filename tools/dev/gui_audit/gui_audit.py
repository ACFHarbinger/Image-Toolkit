"""Static structural audit of gui/src: mixin stacks, long functions, duplicate def names, file sizes."""
import ast, collections, os, sys

ROOT = sys.argv[1]
files = []
for dp, dn, fn in os.walk(ROOT):
    if "__pycache__" in dp:
        continue
    for f in fn:
        if f.endswith(".py"):
            files.append(os.path.join(dp, f))

classes = []          # (bases_count, name, relpath, bases)
long_funcs = []       # (lines, qualname, relpath)
def_names = collections.defaultdict(list)  # name -> [relpath]
big_files = []
signals_per_worker = []
qwidget_first = []
for path in files:
    rel = os.path.relpath(path, ROOT)
    try:
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
    except Exception as e:
        print("PARSE FAIL", rel, e)
        continue
    n = src.count("\n") + 1
    if n > 500:
        big_files.append((n, rel))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = [ast.unparse(b) for b in node.bases]
            classes.append((len(bases), node.name, rel, bases))
            if len(bases) >= 3 and bases[0] in ("QWidget", "QMainWindow", "QDialog", "QObject"):
                qwidget_first.append((node.name, rel, bases[0]))
            # signals on QThread/QRunnable workers
            if any(b in ("QThread", "QRunnable", "QObject") for b in bases):
                sigs = [t.targets[0].id for t in node.body
                        if isinstance(t, ast.Assign) and isinstance(t.value, ast.Call)
                        and ast.unparse(t.value.func) == "Signal" and isinstance(t.targets[0], ast.Name)]
                if sigs:
                    signals_per_worker.append((node.name, rel, sigs))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            if length > 80:
                long_funcs.append((length, node.name, rel))
            def_names[node.name].append(rel)

print("=== FILES >500 LOC (%d) ===" % len(big_files))
for n, r in sorted(big_files, reverse=True):
    print(f"{n:5d}  {r}")

print("\n=== CLASSES WITH >=5 BASES (mixin stacks) ===")
for cnt, name, rel, bases in sorted(classes, reverse=True):
    if cnt >= 5:
        print(f"{cnt:2d}  {name:40s} {rel}")

print("\n=== Qt class FIRST in a >=3-base MRO (MRO-rule violations) ===")
for name, rel, b in qwidget_first:
    print(f"  {name:40s} {rel}  (first base={b})")

print("\n=== FUNCTIONS >80 LINES (%d) ===" % len(long_funcs))
for n, name, rel in sorted(long_funcs, reverse=True)[:40]:
    print(f"{n:4d}  {name:40s} {rel}")

print("\n=== DEF NAMES DEFINED IN >=6 FILES (DRY candidates; dunder/test excluded) ===")
for name, rels in sorted(def_names.items(), key=lambda kv: -len(kv[1])):
    if name.startswith("__") or len(rels) < 6:
        continue
    print(f"{len(rels):3d}  {name}")

print("\n=== WORKER SIGNAL SETS (signature clusters) ===")
clusters = collections.defaultdict(list)
for name, rel, sigs in signals_per_worker:
    clusters[tuple(sorted(sigs))].append(f"{name} ({rel})")
for sigs, members in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
    if len(members) >= 2:
        print(f"{len(members):2d}x  {sigs}")
        for m in members:
            print("       ", m)
print("\nTotal worker-like classes with Signals:", len(signals_per_worker))
