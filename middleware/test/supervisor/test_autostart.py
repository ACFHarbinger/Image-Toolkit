"""Linux XDG autostart desktop file (#877)."""

from __future__ import annotations

from middleware.src.supervisor.autostart import (
    DESKTOP_NAME,
    disable,
    enable,
    is_enabled,
)


def test_enable_and_disable(tmp_path) -> None:
    config_home = tmp_path / "config"
    data_dir = tmp_path / "data"
    path = enable(
        data_dir=data_dir,
        config_home=config_home,
        exec_argv=["/usr/bin/python", "-m", "middleware.src.supervisor", "--data-dir", str(data_dir)],
    )
    assert path.name == DESKTOP_NAME
    assert is_enabled(config_home) is True
    text = path.read_text(encoding="utf-8")
    assert "Type=Application" in text
    assert "X-GNOME-Autostart-enabled=true" in text
    assert str(data_dir) in text
    disable(config_home)
    assert is_enabled(config_home) is False
