"""Krita entry point for the Cel-Shaded learning tutor."""

from krita import DockWidgetFactory, DockWidgetFactoryBase, Krita

from .color_docker import CharacterColorsDocker
from .docker import LearningDocker

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
