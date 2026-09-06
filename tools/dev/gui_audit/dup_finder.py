"""Cross-file duplicate-block finder: hashes sliding windows of N normalized lines."""
import collections, hashlib, os, re, sys

ROOT, N = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 12
skip = re.compile(r'^\s*(#|"""|\'\'\'|$|from |import |\)|\]|\}|else:|try:|pass$|return$)')

def norm(line):
    s = line.strip()
    s = re.sub(r'"[^"]*"', '""', s)
    s = re.sub(r"'[^']*'", "''", s)
    return s

index = collections.defaultdict(set)  # hash -> {(file, startline)}
for dp, dn, fn in os.walk(ROOT):
    if "__pycache__" in dp:
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, ROOT)
        lines = open(p, encoding="utf-8").read().splitlines()
        kept = [(i + 1, norm(l)) for i, l in enumerate(lines) if not skip.match(l) and len(l.strip()) > 3]
        for i in range(len(kept) - N + 1):
            window = "\n".join(t for _, t in kept[i:i + N])
            h = hashlib.md5(window.encode()).hexdigest()
            index[h].add((rel, kept[i][0]))

# collapse overlapping windows: keep only pairs of files, count distinct windows
pairs = collections.Counter()
examples = {}
for h, locs in index.items():
    files = sorted({f for f, _ in locs})
    if len(files) < 2:
        continue
    for a in range(len(files)):
        for b in range(a + 1, len(files)):
            pairs[(files[a], files[b])] += 1
            examples.setdefault((files[a], files[b]), sorted(locs)[:2])

print(f"window={N} normalized lines; cross-file duplicate windows by file pair (top 60):")
for (a, b), c in pairs.most_common(60):
    ex = examples[(a, b)]
    print(f"{c:4d}  {a}  <->  {b}   e.g. {ex[0][0]}:{ex[0][1]} / {ex[1][0]}:{ex[1][1]}")
