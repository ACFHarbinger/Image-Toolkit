"""Legacy migration tests (W0-16 / #880)."""

from __future__ import annotations

import pytest

from middleware.src.settings import (
    ConflictPolicy,
    MigrationConflictError,
    SettingScope,
    SettingsService,
)
from middleware.src.settings.adapters import JsonFileStore, MemoryStore
from middleware.src.settings.migration import (
    MigrationError,
    backup_legacy_file,
    migrate_legacy,
    read_legacy_qsettings,
)

LEGACY_INI = """[General]
theme=light
preferences/recursive_scan=true

[mainwindow]
geometry=@ByteArray(\\x01\\x02\\x03)

[preferences]
initial_cache_maxsize=300
restore_last_dir=false
"""


def _service(tmp_path) -> SettingsService:
    return SettingsService(
        stores={
            SettingScope.DEVICE: JsonFileStore(tmp_path / "device.json"),
            SettingScope.ACCOUNT: JsonFileStore(tmp_path / "account.json"),
            SettingScope.SESSION: MemoryStore(),
        }
    )


def _legacy_file(tmp_path) -> object:
    path = tmp_path / "ImageToolkit.conf"
    path.write_text(LEGACY_INI, encoding="utf-8")
    return path


def test_read_legacy_qsettings_flattens_sections(tmp_path) -> None:
    path = _legacy_file(tmp_path)
    entries = read_legacy_qsettings(path)
    assert entries["theme"] == "light"
    assert entries["preferences/recursive_scan"] is True
    assert entries["preferences/initial_cache_maxsize"] == 300
    assert entries["preferences/restore_last_dir"] is False
    assert entries["mainwindow/geometry"] == "@ByteArray(\\x01\\x02\\x03)"


def test_backup_happens_first_and_original_is_untouched(tmp_path) -> None:
    path = _legacy_file(tmp_path)
    before = path.read_text(encoding="utf-8")
    backup = backup_legacy_file(path)
    assert backup.is_file()
    assert backup.name.startswith("ImageToolkit.conf.")
    assert backup.name.endswith(".bak")
    assert path.read_text(encoding="utf-8") == before  # original never modified


def test_backup_missing_file_raises(tmp_path) -> None:
    with pytest.raises(MigrationError):
        backup_legacy_file(tmp_path / "nope.conf")


def test_migrate_imports_values(tmp_path) -> None:
    service = _service(tmp_path)
    path = _legacy_file(tmp_path)
    report = migrate_legacy(service, path)
    assert sorted(report.migrated_keys) == [
        "mainwindow/geometry",
        "preferences/initial_cache_maxsize",
        "preferences/recursive_scan",
        "preferences/restore_last_dir",
        "theme",
    ]
    assert report.conflicts == []
    assert service.get("theme") == "light"
    assert service.get("preferences/initial_cache_maxsize") == 300
    assert service.get("preferences/restore_last_dir") is False
    assert report.backup_path.is_file()


def test_migration_conflict_aborts_without_writing(tmp_path) -> None:
    service = _service(tmp_path)
    service.set("theme", "dark")  # new store already has a different theme
    path = _legacy_file(tmp_path)

    with pytest.raises(MigrationConflictError) as exc_info:
        migrate_legacy(service, path, policy=ConflictPolicy.ABORT)
    conflict = exc_info.value.conflicts[0]
    assert conflict.key == "theme"
    assert conflict.legacy_value == "light"
    assert conflict.new_value == "dark"
    # nothing from the legacy file landed
    assert not service.contains("preferences/recursive_scan")
    # but the backup was still made (backup always happens first)
    assert any(p.name.endswith(".bak") for p in tmp_path.iterdir())


def test_migration_conflict_policies(tmp_path) -> None:
    # isolated dirs: the backup filename is second-resolution, so two
    # migrations of the same file in one second would collide otherwise
    legacy_a = tmp_path / "a" / "ImageToolkit.conf"
    legacy_a.parent.mkdir()
    legacy_a.write_text(LEGACY_INI, encoding="utf-8")
    legacy_b = tmp_path / "b" / "ImageToolkit.conf"
    legacy_b.parent.mkdir()
    legacy_b.write_text(LEGACY_INI, encoding="utf-8")

    prefer_legacy = _service(tmp_path / "a")
    prefer_legacy.set("theme", "dark")
    report = migrate_legacy(prefer_legacy, legacy_a, policy=ConflictPolicy.PREFER_LEGACY)
    assert prefer_legacy.get("theme") == "light"
    assert [c.key for c in report.conflicts] == ["theme"]

    prefer_new = _service(tmp_path / "b")
    prefer_new.set("theme", "dark")
    report = migrate_legacy(prefer_new, legacy_b, policy=ConflictPolicy.PREFER_NEW)
    assert prefer_new.get("theme") == "dark"  # new value kept
    assert report.skipped_keys == ["theme"]
    assert "theme" not in report.migrated_keys


def test_migration_identical_values_are_not_conflicts(tmp_path) -> None:
    service = _service(tmp_path)
    service.set("theme", "light")  # same value as legacy
    path = _legacy_file(tmp_path)
    report = migrate_legacy(service, path)
    assert report.conflicts == []
    assert "theme" in report.migrated_keys
