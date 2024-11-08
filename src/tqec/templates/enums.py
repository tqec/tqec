"""Defines a few enumerations related to templates."""

from enum import Enum, auto


class TemplateOrientation(Enum):
    """Indicates the orientation of the midline of a template."""

    HORIZONTAL = auto()
    VERTICAL = auto()
