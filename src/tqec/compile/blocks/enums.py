from enum import Enum

from tqec.templates.enums import TemplateBorder
from tqec.utils.position import Direction3D, SignedDirection3D


class SpatialBlockBorder(Enum):
    X_NEGATIVE = SignedDirection3D(Direction3D.X, False)
    X_POSITIVE = SignedDirection3D(Direction3D.X, True)
    Y_NEGATIVE = SignedDirection3D(Direction3D.Y, False)
    Y_POSITIVE = SignedDirection3D(Direction3D.Y, True)

    def to_template_border(self) -> TemplateBorder:
        match self:
            case SpatialBlockBorder.X_NEGATIVE:
                return TemplateBorder.LEFT
            case SpatialBlockBorder.X_POSITIVE:
                return TemplateBorder.RIGHT
            case SpatialBlockBorder.Y_NEGATIVE:
                return TemplateBorder.TOP
            case SpatialBlockBorder.Y_POSITIVE:
                return TemplateBorder.BOTTOM


class TemporalBlockBorder(Enum):
    Z_NEGATIVE = SignedDirection3D(Direction3D.Z, False)
    Z_POSITIVE = SignedDirection3D(Direction3D.Z, True)
