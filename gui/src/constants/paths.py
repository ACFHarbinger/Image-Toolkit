import sys
from pathlib import Path

# Mirror backend/src/constants/paths.py: under a PyInstaller bundle the repo
# layout lives in sys._MEIPASS, so a __file__-relative walk only works from a
# source checkout.
if getattr(sys, "frozen", False):
    ROOT_DIR = (
        Path(sys._MEIPASS)
        if hasattr(sys, "_MEIPASS")
        else Path(sys.executable).resolve().parent
    )
else:
    ROOT_DIR = Path(__file__).resolve().parents[3]

# The bundle root is read-only/transient — never a write target. Keep
# screenshots in the user-data dir when frozen; source checkouts keep the
# historical repo-relative default.
SCREENSHOTS_DIR = str(
    (Path.home() / ".image-toolkit" / "screenshots")
    if getattr(sys, "frozen", False)
    else (ROOT_DIR / "screenshots")
)

# Standalone CRE sub-project, reused by the listings
# embedding/semantic-search/recommendation workers instead of loading a
# second copy of the embedder. Previously redeclared identically in 3 files.
RECOMMENDATION_ENGINE_DIR = ROOT_DIR / "submodules" / "CRE"
