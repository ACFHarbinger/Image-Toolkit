from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
SCREENSHOTS_DIR = str(ROOT_DIR / "screenshots")

# Standalone Recommendation-Engine sub-project, reused by the listings
# embedding/semantic-search/recommendation workers instead of loading a
# second copy of the embedder. Previously redeclared identically in 3 files.
RECOMMENDATION_ENGINE_DIR = ROOT_DIR / "submodules" / "Recommendation-Engine"
