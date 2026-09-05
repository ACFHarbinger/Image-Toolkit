"""Theme-aware usage charts for the Cloud Compute Dashboards pane (#490).

QPainter only (no QtCharts). Colors follow the dataviz categorical set used
in ASP reports (blue / orange / aqua / yellow) and swap for light palettes.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

from backend.src.web.cloud.compute.usage import UsageRow, UsageSummary
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPen
from PySide6.QtWidgets import QWidget

# Validated adjacent categorical order (dataviz skill / ASP reports).
_DARK_SERIES = ("#2a78d6", "#eb6834", "#3dbebf", "#e8c547")
_LIGHT_SERIES = ("#175fb8", "#c24e20", "#1a8a8c", "#b79212")


def chart_theme_from_palette(palette: QPalette) -> dict:
    window = palette.color(QPalette.ColorRole.Window)
    dark = window.lightness() < 140
    text = palette.color(QPalette.ColorRole.WindowText)
    return {
        "dark": dark,
        "bg": window,
        "text": text,
        "grid": QColor(255, 255, 255, 28) if dark else QColor(0, 0, 0, 28),
        "axis": QColor(text.red(), text.green(), text.blue(), 160),
        "series": [QColor(c) for c in (_DARK_SERIES if dark else _LIGHT_SERIES)],
    }


class _BarChart(QWidget):
    """Simple vertical bar chart: list of (label, value)."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._bars: List[Tuple[str, float]] = []
        self.setMinimumHeight(160)

    def set_bars(self, bars: Sequence[Tuple[str, float]]) -> None:
        self._bars = [(str(label), max(0.0, float(value))) for label, value in bars]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = chart_theme_from_palette(self.palette())
        painter.fillRect(self.rect(), theme["bg"])
        font = QFont(self.font())
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(theme["text"])
        painter.drawText(8, 16, self._title)

        plot = QRectF(36, 28, max(8.0, self.width() - 48), max(8.0, self.height() - 48))
        if not self._bars:
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(theme["axis"])
            painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, "No jobs yet")
            return

        peak = max(v for _, v in self._bars) or 1.0
        n = len(self._bars)
        gap = plot.width() * 0.08 / max(n, 1)
        bar_w = (plot.width() - gap * (n + 1)) / n
        axis_pen = QPen(theme["grid"])
        painter.setPen(axis_pen)
        for frac in (0.0, 0.5, 1.0):
            y = plot.bottom() - frac * plot.height()
            painter.drawLine(plot.left(), y, plot.right(), y)

        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        color = theme["series"][0]
        for i, (label, value) in enumerate(self._bars):
            x = plot.left() + gap + i * (bar_w + gap)
            h = (value / peak) * plot.height()
            rect = QRectF(x, plot.bottom() - h, bar_w, h)
            painter.fillRect(rect, color)
            painter.setPen(theme["axis"])
            tick = label if len(label) <= 10 else label[:9] + "…"
            painter.drawText(
                QRectF(x - 4, plot.bottom() + 2, bar_w + 8, 16),
                Qt.AlignmentFlag.AlignHCenter,
                tick,
            )
        painter.end()


class _GroupedBarChart(QWidget):
    """One group per provider; three series (jobs, duration s, cost ¢)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._groups: List[Tuple[str, Tuple[float, float, float]]] = []
        self.setMinimumHeight(160)

    def set_groups(self, groups: Sequence[Tuple[str, Tuple[float, float, float]]]) -> None:
        self._groups = list(groups)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = chart_theme_from_palette(self.palette())
        painter.fillRect(self.rect(), theme["bg"])
        font = QFont(self.font())
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(theme["text"])
        painter.drawText(8, 16, "Provider comparison (jobs / duration / cost)")

        plot = QRectF(36, 28, max(8.0, self.width() - 48), max(8.0, self.height() - 52))
        if not self._groups:
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(theme["axis"])
            painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, "No jobs yet")
            return

        peaks = [1.0, 1.0, 1.0]
        for _, vals in self._groups:
            for i, v in enumerate(vals):
                peaks[i] = max(peaks[i], v)
        n = len(self._groups)
        group_w = plot.width() / n
        bar_w = group_w / 5
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        for gi, (label, vals) in enumerate(self._groups):
            gx = plot.left() + gi * group_w + group_w * 0.2
            for si, value in enumerate(vals):
                h = (value / peaks[si]) * plot.height()
                rect = QRectF(gx + si * bar_w, plot.bottom() - h, bar_w * 0.9, h)
                painter.fillRect(rect, theme["series"][si % len(theme["series"])])
            painter.setPen(theme["axis"])
            painter.drawText(
                QRectF(plot.left() + gi * group_w, plot.bottom() + 2, group_w, 16),
                Qt.AlignmentFlag.AlignHCenter,
                label,
            )
        painter.end()


def bars_from_duration(rows: Sequence[UsageRow], limit: int = 12) -> List[Tuple[str, float]]:
    slice_ = list(rows)[-limit:]
    return [(row.job_id or f"#{i+1}", row.duration_seconds) for i, row in enumerate(slice_)]


def groups_from_summary(summary: UsageSummary) -> List[Tuple[str, Tuple[float, float, float]]]:
    out = []
    for name, stats in summary.by_provider.items():
        out.append(
            (
                name.upper() or "?",
                (float(stats.jobs), stats.duration_seconds, stats.cost_usd * 100.0),
            )
        )
    return out


__all__ = [
    "bars_from_duration",
    "chart_theme_from_palette",
    "groups_from_summary",
    "_BarChart",
    "_GroupedBarChart",
]
