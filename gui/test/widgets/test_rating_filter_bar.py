import sys

from gui.src.components.widgets.rating_filter_bar import RatingFilterBar
from gui.src.windows.settings.app_settings import AppSettings
from PySide6.QtWidgets import QApplication

if not QApplication.instance():
    app = QApplication(sys.argv)


def test_rating_filter_bar_initial_state():
    bar = RatingFilterBar()
    assert bar.min_rating == 0
    assert bar.selected_color_label is None
    assert bar.matches(rating=None, label=None)
    assert bar.matches(rating=3.0, label="blue")


def test_rating_filter_bar_star_filtering():
    bar = RatingFilterBar()
    signals: list[tuple[int, object]] = []
    bar.filter_changed.connect(lambda r, l: signals.append((r, l)))

    # Click 3+ stars
    bar._on_star_clicked(3)
    assert bar.min_rating == 3
    assert len(signals) == 1
    assert signals[0] == (3, None)

    assert not bar.matches(rating=2.5, label=None)
    assert bar.matches(rating=3.0, label=None)
    assert bar.matches(rating=4.5, label="red")


def test_rating_filter_bar_label_filtering():
    bar = RatingFilterBar()
    signals: list[tuple[int, object]] = []
    bar.filter_changed.connect(lambda r, l: signals.append((r, l)))

    # Click green label
    bar._on_label_clicked("green")
    assert bar.selected_color_label == "green"
    assert signals[-1] == (0, "green")

    assert bar.matches(label="green")
    assert not bar.matches(label="blue")
    assert not bar.matches(label=None)

    # Click green again to toggle off
    bar._on_label_clicked("green")
    assert bar.selected_color_label is None
    assert bar.matches(label="blue")


def test_rating_filter_bar_reset():
    bar = RatingFilterBar()
    bar._on_star_clicked(4)
    bar._on_label_clicked("red")
    assert bar.min_rating == 4
    assert bar.selected_color_label == "red"

    bar.reset_filters()
    assert bar.min_rating == 0
    assert bar.selected_color_label is None


def test_app_settings_star_rating():
    path = "/dummy/test/image.png"
    AppSettings.set_star_rating(path, 4.5)
    assert AppSettings.star_rating(path) == 4.5
    AppSettings.remove(f"ratings/{path}")
    assert AppSettings.star_rating(path) is None
