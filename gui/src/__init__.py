"""``gui.src`` package.

Importing it installs the non-native ``QFileDialog`` patch process-wide
(ui-arch-29/#551) — the one place it happens; entry points and test
configuration no longer call ``apply_patch()`` themselves.
"""

from gui.src.file_dialog_patch import apply_patch as _apply_file_dialog_patch
import gui.src.legacy  # noqa: F401 - bootstrap legacy submodule Qt trees

_apply_file_dialog_patch()
