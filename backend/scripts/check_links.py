import os
import re
import sys
import urllib.parse
from pathlib import Path

root = Path(__file__).resolve().parent.parent

# Only scan these specific patterns/paths
paths_to_scan = [
    root / "README.md",
    root / "CLAUDE.md",
    root / "GEMINI.md"
]
for folder in ["moon", "reports"]:
    paths_to_scan.extend(root.glob(f"{folder}/**/*.md"))

for f in root.glob("docs/**/*.md"):
    if any(p in f.parts for p in ["roadmaps", "reports", "api"]) or f.name.lower() == "readme.md":
        continue
    paths_to_scan.append(f)

broken_count = 0
for f in paths_to_scan:
    if not f.exists():
        continue
    try:
        content = f.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        print(f"Could not read {f}: {e}")
        continue
        
    # Strip fenced code blocks (``` ... ```) before link scanning so that
    # C++ lambda syntax like [&](auto&&) is not misread as a Markdown link.
    stripped = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    # Also strip inline code spans to be safe.
    stripped = re.sub(r'`[^`\n]+`', '', stripped)

    for match in re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', stripped):
        text = match.group(1)
        url = match.group(2).strip()
        
        # Split off markdown title if any (e.g. [Link](url "title"))
        parts = url.split(None, 1)
        url = parts[0]
        
        # Ignore external links, mailto, anchor links, etc.
        if url.startswith(("http://", "https://", "mailto:", "ftp:", "git:", "ssh:", "#")):
            continue
            
        url = urllib.parse.unquote(url)
        url_parsed = urllib.parse.urlparse(url)
        path_part = url_parsed.path
        
        if not path_part:
            continue
            
        target = (f.parent / path_part).resolve()
        
        if not target.exists():
            try:
                rel_target = target.relative_to(root)
            except ValueError:
                rel_target = target
            print(f"Broken link in {f.relative_to(root)}: {match.group(0)} -> target {rel_target} does not exist")
            broken_count += 1

print(f"Total broken links found: {broken_count}")
if broken_count > 0:
    sys.exit(1)
else:
    sys.exit(0)
