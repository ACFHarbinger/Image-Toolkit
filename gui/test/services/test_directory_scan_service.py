"""Tests for the shared directory-scan service (ui-arch-39 / #561, R1.6).

Covers the pure ``collect_files`` walk (flat/recursive, extension
normalization, edge paths, cancellation), the ``DirectoryScanWorker``
base-class contract (payload delivery, pre-cancel → ``None``), and the
``ScanSession`` generation token (increasing generations, cancel clears
the in-flight worker, one live delivery).
"""

from __future__ import annotations

import pytest
from gui.src.helpers.core.directory_scan_worker import DirectoryScanWorker
from gui.src.services.directory_scan_service import (
    ScanRequest,
    ScanSession,
    collect_files,
    normalize_extensions,
)
from PySide6.QtCore import QEventLoop, QTimer


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "a.JPG").write_bytes(b"1")
    (tmp_path / "b.png").write_bytes(b"2")
    (tmp_path / "c.txt").write_bytes(b"3")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "d.jpg").write_bytes(b"4")
    (sub / "e.mp4").write_bytes(b"5")
    return tmp_path


def test_normalize_extensions():
    assert normalize_extensions({"JPG", ".png", " .gif ", "", "  "}) == frozenset({"jpg", "png", "gif"})
    assert normalize_extensions(None) == frozenset()
    assert normalize_extensions([]) == frozenset()


def test_collect_flat(tree):
    found = collect_files(ScanRequest(path=str(tree), extensions={"jpg", "png"}))
    names = sorted(p.rsplit("/", 1)[-1] for p in found)
    assert names == ["a.JPG", "b.png"]


def test_collect_flat_no_nested(tree):
    found = collect_files(ScanRequest(path=str(tree), extensions={"jpg"}))
    assert len(found) == 1 and found[0].endswith("a.JPG")


def test_collect_recursive(tree):
    found = collect_files(ScanRequest(path=str(tree), extensions={"jpg"}, recursive=True))
    names = sorted(p.rsplit("/", 1)[-1] for p in found)
    assert names == ["a.JPG", "d.jpg"]


def test_collect_empty_filter_matches_all(tree):
    found = collect_files(ScanRequest(path=str(tree)))
    assert len(found) == 3


def test_collect_missing_and_empty_paths(tmp_path):
    assert collect_files(ScanRequest(path=str(tmp_path / "nope"))) == []
    assert collect_files(ScanRequest(path="")) == []


def test_collect_single_file(tree):
    target = str(tree / "a.JPG")
    assert collect_files(ScanRequest(path=target)) == []
    assert collect_files(ScanRequest(path=target, extensions={"jpg"}, accept_single_file=True)) == [target]


def test_collect_hidden_policy(tree):
    hidden = tree / ".hidden.jpg"
    hidden.write_bytes(b"h")
    all_found = collect_files(ScanRequest(path=str(tree), extensions={"jpg"}, recursive=True))
    assert any(p.endswith(".hidden.jpg") for p in all_found)
    visible = collect_files(ScanRequest(path=str(tree), extensions={"jpg"}, recursive=True, skip_hidden=True))
    assert not any(p.endswith(".hidden.jpg") for p in visible)


def test_collect_cancelled_upfront(tree):
    found = collect_files(
        ScanRequest(path=str(tree), extensions={"jpg"}, recursive=True),
        is_cancelled=lambda: True,
    )
    assert found == []


def test_collect_symlink_policy(tree, tmp_path):
    target = tree / "a.JPG"
    link_file = tmp_path / "link.jpg"
    link_dir = tmp_path / "linkdir"
    try:
        link_file.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    (tmp_path / "real").mkdir(exist_ok=True)
    (tmp_path / "real" / "inner.jpg").write_bytes(b"i")
    try:
        link_dir.symlink_to(tmp_path / "real", target_is_directory=True)
    except OSError:
        pytest.skip("dir symlinks unavailable")
    flat = collect_files(ScanRequest(path=str(tmp_path), extensions={"jpg"}))
    assert any(p.endswith("link.jpg") for p in flat)
    recursive = collect_files(ScanRequest(path=str(tmp_path), extensions={"jpg"}, recursive=True))
    assert any(p.endswith("inner.jpg") for p in recursive)
    assert not any("linkdir" in p for p in recursive)
    followed = collect_files(
        ScanRequest(
            path=str(tmp_path),
            extensions={"jpg"},
            recursive=True,
            follow_symlinks=True,
        )
    )
    assert any("linkdir" in p for p in followed)


def test_collect_mid_scan_cancel(tree):
    calls = 0

    def _cancel_after_first() -> bool:
        nonlocal calls
        calls += 1
        return calls > 200

    found = collect_files(ScanRequest(path=str(tree), recursive=True), is_cancelled=_cancel_after_first)
    assert isinstance(found, list)


def test_worker_execute_returns_paths(tree):
    worker = DirectoryScanWorker(ScanRequest(path=str(tree), extensions={"jpg", "png"}))
    try:
        result = worker._execute()
    finally:
        worker.deleteLater()
    assert sorted(result or []) == sorted(collect_files(ScanRequest(path=str(tree), extensions={"jpg", "png"})))


def test_worker_precancelled_returns_none(tree):
    worker = DirectoryScanWorker(ScanRequest(path=str(tree), recursive=True))
    try:
        worker.cancel()
        assert worker._execute() is None
    finally:
        worker.deleteLater()


def test_worker_run_emits_finished_payload(tree):
    worker = DirectoryScanWorker(ScanRequest(path=str(tree), extensions={"png"}))
    received = []
    worker.finished.connect(received.append)
    try:
        worker.run()
    finally:
        worker.deleteLater()
    assert len(received) == 1
    assert received[0] is not None and received[0][0].endswith("b.png")


def test_worker_run_precancelled_emits_none(tree):
    worker = DirectoryScanWorker(ScanRequest(path=str(tree)))
    received = []
    errors = []
    worker.finished.connect(received.append)
    worker.error.connect(errors.append)
    try:
        worker.cancel()
        worker.run()
    finally:
        worker.deleteLater()
    assert received == [None]
    assert errors == []


def test_session_generations_and_cancel(tree):
    session = ScanSession()
    first = session.scan(ScanRequest(path=str(tree), recursive=True), lambda paths: None)
    assert first == 1
    assert session.generation == 1
    session.cancel()
    second = session.scan(ScanRequest(path=str(tree)), lambda paths: None)
    assert second == 2
    assert session.generation == 2
    session.cancel()


def test_session_stale_delivery_dropped(tree):
    # A duplicate delivery from a superseded generation must not reach
    # the old callback, even if its worker was already retired.
    session = ScanSession()
    received = []
    session.scan(ScanRequest(path=str(tree)), received.append)
    session.cancel()
    session.scan(ScanRequest(path=str(tree)), received.append)
    session.cancel()
    session._on_ready((1, ["late.jpg"]))
    assert received == []


def test_session_delivers_once(tree):
    session = ScanSession()
    received = []
    loop = QEventLoop()
    session.scan(
        ScanRequest(path=str(tree), extensions={"txt"}),
        lambda paths: (received.append(paths), loop.quit()),
    )
    QTimer.singleShot(10000, loop.quit)
    loop.exec()
    session.cancel()
    assert len(received) == 1
    assert received[0][0].endswith("c.txt")
