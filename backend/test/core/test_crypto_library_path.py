"""Native crypto artifact discovery regressions."""

from pathlib import Path

from backend.src.constants import paths


def test_base_build_crypto_library_has_priority_over_legacy_build():
    root_library = paths.ROOT_DIR / paths._crypto_lib_name
    legacy_library = paths.ROOT_DIR / "build" / "crypto" / paths._crypto_lib_name

    if root_library.exists() and legacy_library.exists():
        assert Path(paths.resolve_crypto_lib_file()) == root_library


def test_worktree_resolves_crypto_from_main_checkout(tmp_path, monkeypatch):
    """A linked git worktree must find libitk_crypto.so in the main clone
    (D12 worktrees do not copy `just build-base` artifacts)."""
    main = tmp_path / "main"
    worktree = tmp_path / "worktree"
    main.mkdir()
    worktree.mkdir()
    so = main / paths._crypto_lib_name
    so.write_bytes(b"fake")
    gitdir = main / ".git" / "worktrees" / "d12"
    gitdir.mkdir(parents=True)
    (worktree / ".git").write_text(f"gitdir: {gitdir}\n")
    monkeypatch.setattr(paths, "ROOT_DIR", worktree)
    assert Path(paths.resolve_crypto_lib_file()) == so
