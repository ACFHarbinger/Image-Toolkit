"""Shared dark-theme matplotlib styling + a Qt-embeddable canvas, kept
visually consistent with ``bench_anime_stitch.py``'s own plot styling
(``#12121f`` figure background, white text/ticks, inferno/plasma/hot
colormaps) so the dashboard's live visualizations read as the same tool
family as its static report plots.
"""

from __future__ import annotations

from typing import List, Tuple, Union

import matplotlib

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from ..constants.user_interface import FIG_BG, AX_BG


def _style_axis(ax) -> None:
    ax.set_facecolor(AX_BG)
    ax.title.set_color("white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")


def themed_figure(
    figsize: Tuple[float, float] = (6.0, 4.5), n_axes: int = 1, projection: str = None
) -> Union[Tuple[Figure, object], Tuple[Figure, List]]:
    fig = Figure(figsize=figsize, dpi=100)
    fig.patch.set_facecolor(FIG_BG)
    if n_axes == 1:
        ax = fig.add_subplot(111, projection=projection)
        _style_axis(ax)
        return fig, ax
    axes = [fig.add_subplot(1, n_axes, i + 1) for i in range(n_axes)]
    for ax in axes:
        _style_axis(ax)
    return fig, axes


class PlotCanvas(FigureCanvasQTAgg):
    """Thin wrapper so callers never need to import matplotlib's Qt backend
    directly — every visualization/comparison module returns a ``Figure``
    and hands it to this one canvas type."""

    def __init__(self, fig: Figure, parent=None):
        super().__init__(fig)
        if parent is not None:
            self.setParent(parent)
