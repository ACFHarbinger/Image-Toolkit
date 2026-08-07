"""Krita entry point for the Cel-Shaded learning tutor."""

from krita import DockWidgetFactory, DockWidgetFactoryBase, Krita

from .chapter_docker import ChapterQueueDocker
from .color_docker import CharacterColorsDocker
from .docker import LearningDocker
from .segmentation_docker import SegmentationDocker

Krita.instance().addDockWidgetFactory(
    DockWidgetFactory(
        "cel_shaded_generator_learning_docker",
        DockWidgetFactoryBase.DockRight,
        LearningDocker,
    )
)
Krita.instance().addDockWidgetFactory(
    DockWidgetFactory(
        "cel_shaded_generator_character_colors_docker",
        DockWidgetFactoryBase.DockRight,
        CharacterColorsDocker,
    )
)
Krita.instance().addDockWidgetFactory(
    DockWidgetFactory(
        "cel_shaded_generator_segmentation_docker",
        DockWidgetFactoryBase.DockRight,
        SegmentationDocker,
    )
)
Krita.instance().addDockWidgetFactory(
    DockWidgetFactory(
        "cel_shaded_generator_chapter_queue_docker",
        DockWidgetFactoryBase.DockRight,
        ChapterQueueDocker,
    )
)
