"""PillowGifPlayer loops frames without QMovie."""

import time

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from gui.src.helpers.image.gif_player import PillowGifPlayer

pytestmark = pytest.mark.gui


def test_pillow_gif_player_advances_and_loops(q_app, tmp_path):
    red = Image.new("RGB", (8, 8), (255, 0, 0))
    green = Image.new("RGB", (8, 8), (0, 255, 0))
    path = tmp_path / "loop.gif"
    red.save(path, save_all=True, append_images=[green], duration=30, loop=0)

    seen = []
    player = PillowGifPlayer()
    player.frame_ready.connect(lambda img: seen.append((img.width(), img.height())))
    assert player.start(str(path), max_edge=32)
    deadline = time.time() + 1.0
    while player._index < 1 and time.time() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    assert player._index >= 1
    assert seen
    assert seen[0] == (8, 8)
    player.stop()
    assert not player.is_running()
