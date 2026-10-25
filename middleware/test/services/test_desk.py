from __future__ import annotations

import os
from pathlib import Path

from middleware.src.services.desk.logs import read_log
from middleware.src.services.desk.metadata import describe_file


def test_missing_log_is_not_created(tmp_path: Path) -> None:
    missing = tmp_path / "nope.log"
    result = read_log(str(missing), 50)
    assert result == {
        "found": False,
        "path": str(missing),
        "lines": [],
        "error_count": 0,
        "reason": "log file is missing",
    }
    assert not missing.exists()


def test_last_two_lines_count_one_error(tmp_path: Path) -> None:
    log = tmp_path / "app.log"
    payload = b"INFO hello\nERROR boom\nnote done\n"
    log.write_bytes(payload)
    result = read_log(str(log), 2)
    assert result["found"] is True
    assert result["lines"] == ["ERROR boom", "note done"]
    assert result["error_count"] == 1
    assert result["reason"] == "log is not followed"
    assert log.read_bytes() == payload


def test_error_count_is_a_whole_word(tmp_path: Path) -> None:
    log = tmp_path / "words.log"
    log.write_text("ERRORS only\nERROR\nsee ERROR now\n", encoding="utf-8")
    result = read_log(str(log), 3)
    assert result["lines"] == ["ERRORS only", "ERROR", "see ERROR now"]
    assert result["error_count"] == 2


def test_directory_and_symlink_are_not_followed(tmp_path: Path) -> None:
    assert read_log(str(tmp_path), 10)["found"] is False
    target = tmp_path / "real.log"
    target.write_text("ERROR x\n", encoding="utf-8")
    link = tmp_path / "link.log"
    link.symlink_to(target)
    assert read_log(str(link), 10)["found"] is False
    assert target.read_text(encoding="utf-8") == "ERROR x\n"


def test_toolkit_log_is_not_opened(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    log = home / ".image-toolkit" / "app.log"
    log.parent.mkdir(parents=True)
    log.write_text("ERROR secret\n", encoding="utf-8")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    def refuse(*_args, **_kwargs):
        raise AssertionError("log open")

    monkeypatch.setattr(os, "open", refuse)
    result = read_log(str(log), 10)
    assert result["found"] is False
    assert result["reason"] == "log file is missing"


def test_tail_is_capped_at_one_mebibyte(tmp_path: Path) -> None:
    log = tmp_path / "huge.log"
    log.write_bytes(b"A" * (1024 * 1024) + b"\nERROR tail\n")
    before = log.stat().st_size
    result = read_log(str(log), 10)
    assert result["lines"] == ["ERROR tail"]
    assert result["error_count"] == 1
    assert result["reason"] == "log is not followed"
    assert log.stat().st_size == before


def test_missing_metadata(tmp_path: Path) -> None:
    missing = tmp_path / "nope.txt"
    result = describe_file(str(missing))
    assert result == {
        "found": False,
        "path": str(missing),
        "name": "",
        "size": 0,
        "suffix": "",
        "reason": "file is missing",
    }
    assert not missing.exists()


def test_describes_name_size_suffix_without_writing(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    payload = b"abcd"
    path.write_bytes(payload)
    result = describe_file(str(path))
    assert result["found"] is True
    assert result["name"] == "note.txt"
    assert result["size"] == 4
    assert result["suffix"] == ".txt"
    assert result["reason"] == "metadata is not edited"
    assert path.read_bytes() == payload


def test_library_db_is_not_read(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "library.db"
    payload = b"not a database"
    db.write_bytes(payload)

    def refuse(*_args, **_kwargs):
        raise AssertionError("opened")

    monkeypatch.setattr(os, "open", refuse)
    result = describe_file(str(db))
    assert result["found"] is True
    assert result["name"] == "library.db"
    assert result["size"] == len(payload)
    assert result["suffix"] == ".db"
    assert db.stat().st_size == len(payload)
