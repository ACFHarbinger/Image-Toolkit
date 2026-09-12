"""Regression test for R3.2 / ui-arch-47 (#569): zero module-level heavy imports in gui/src.

Asserts that no GUI module in gui/src imports cv2, PIL, numpy, torch, or
torchvision at module scope, preventing hundreds of MBs in startup memory
overhead before login and category activation.
"""

from pathlib import Path

from tools.dev.gui_audit.check_no_module_heavy_imports import find_heavy_imports


def test_no_module_heavy_imports_in_gui_src():
    repo_root = Path(__file__).resolve().parents[2]
    gui_src = repo_root / "gui" / "src"
    assert gui_src.is_dir(), f"gui/src not found at {gui_src}"

    violations = find_heavy_imports(gui_src)
    assert not violations, f"Found {len(violations)} module-level heavy import(s) in gui/src:\n" + "\n".join(
        f"  - {v}" for v in violations
    )


def test_heavy_import_checker_flags_violations(tmp_path: Path):
    bad_file = tmp_path / "bad_module.py"
    bad_file.write_text(
        "import cv2\n"
        "from PIL import Image\n"
        "import numpy as np\n"
        "import torch\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    import torchvision\n",
        encoding="utf-8",
    )
    violations = find_heavy_imports(tmp_path)
    # The 4 top-level imports should be flagged; the TYPE_CHECKING one should not.
    assert len(violations) == 4
    assert any("import cv2" in v for v in violations)
    assert any("from PIL import Image" in v for v in violations)
    assert any("import numpy as np" in v for v in violations)
    assert any("import torch" in v for v in violations)
