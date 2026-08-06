"""Krita entry point for the Cel-Shaded learning tutor."""

from krita import DockWidgetFactory, DockWidgetFactoryBase, Krita

from .docker import LearningDocker

Krita.instance().addDockWidgetFactory(
    DockWidgetFactory(
        "cel_shaded_generator_learning_docker",
        DockWidgetFactoryBase.DockRight,
        LearningDocker,
    )
)
