"""Tests for the scoped Krita plugin installer."""

from integrations.krita.install import install, uninstall


def test_install_and_uninstall_are_scoped(tmp_path):
    unrelated = tmp_path / "other.desktop"
    unrelated.write_text("keep", encoding="utf-8")

    install(tmp_path)
    assert (tmp_path / "cel_shaded_generator.desktop").is_file()
    assert (tmp_path / "cel_shaded_generator" / "content" / "lesson.json").is_file()

    uninstall(tmp_path)
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert not (tmp_path / "cel_shaded_generator.desktop").exists()
    assert not (tmp_path / "cel_shaded_generator").exists()


def test_installer_refuses_to_overwrite_existing_plugin(tmp_path):
    (tmp_path / "cel_shaded_generator").mkdir()

    try:
        install(tmp_path)
    except FileExistsError as error:
        assert "uninstall" in str(error)
    else:
        raise AssertionError("installer overwrote an existing plugin")
