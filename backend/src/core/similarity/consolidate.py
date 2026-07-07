"""Space reclamation without deletion: hardlink/symlink consolidation.

Replaces each duplicate with an OS-level link to the keeper so directory
layouts stay intact while the bytes are stored once. Hardlinks require the
same filesystem; the caller can fall back to symlinks across devices.
"""

import logging
import os
import tempfile
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class ConsolidateResult:
    linked: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    bytes_reclaimed: int = 0


def _same_filesystem(a: str, b: str) -> bool:
    try:
        return os.stat(a).st_dev == os.stat(os.path.dirname(b) or ".").st_dev
    except OSError:
        return False


def _atomic_replace_with_link(keeper: str, duplicate: str, symlink: bool):
    """Create the link at a temp name in the same directory, then atomically
    rename over the duplicate — never leaves a window with no file present."""
    dup_dir = os.path.dirname(duplicate) or "."
    fd, tmp = tempfile.mkstemp(dir=dup_dir, prefix=".itk-link-")
    os.close(fd)
    os.unlink(tmp)
    try:
        if symlink:
            os.symlink(os.path.abspath(keeper), tmp)
        else:
            os.link(keeper, tmp)
        os.replace(tmp, duplicate)
    except OSError:
        if os.path.lexists(tmp):
            os.unlink(tmp)
        raise


def consolidate_cluster(
    keeper: str,
    duplicates: List[str],
    mode: str = "hardlink",   # "hardlink" | "symlink" | "auto"
) -> ConsolidateResult:
    """Replace every path in *duplicates* with a link to *keeper*.

    ``auto`` uses hardlinks when on the same filesystem, symlinks otherwise.
    Files already hardlinked to the keeper are skipped.
    """
    res = ConsolidateResult()
    if not os.path.isfile(keeper):
        res.errors.append(f"keeper missing: {keeper}")
        return res
    keeper_stat = os.stat(keeper)

    for dup in duplicates:
        if os.path.abspath(dup) == os.path.abspath(keeper):
            res.skipped.append(dup)
            continue
        try:
            st = os.stat(dup)
            if st.st_ino == keeper_stat.st_ino and st.st_dev == keeper_stat.st_dev:
                res.skipped.append(dup)   # already the same inode
                continue

            use_symlink = mode == "symlink" or (
                mode == "auto" and not _same_filesystem(keeper, dup)
            )
            if mode == "hardlink" and not _same_filesystem(keeper, dup):
                res.errors.append(f"{dup}: cross-device hardlink not possible")
                continue

            _atomic_replace_with_link(keeper, dup, use_symlink)
            res.linked.append(dup)
            res.bytes_reclaimed += st.st_size
        except OSError as e:
            logger.warning("Consolidation failed for %s: %s", dup, e)
            res.errors.append(f"{dup}: {e}")
    return res
