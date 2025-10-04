from enum import Enum

from tqec.templates.enums import TemplateBorder
from tqec.utils.position import Direction3D, SignedDirection3D


class SpatialBlockBorder(Enum):
    """Enumerates the 4 different spatial borders for a block."""

    X_NEGATIVE = SignedDirection3D(Direction3D.X, False)
    X_POSITIVE = SignedDirection3D(Direction3D.X, True)
    Y_NEGATIVE = SignedDirection3D(Direction3D.Y, False)
    Y_POSITIVE = SignedDirection3D(Direction3D.Y, True)

    def to_template_border(self) -> TemplateBorder:
        """Return the template border corresponding to ``self``."""
        match self:
            case SpatialBlockBorder.X_NEGATIVE:
                return TemplateBorder.LEFT
            case SpatialBlockBorder.X_POSITIVE:
                return TemplateBorder.RIGHT
            case SpatialBlockBorder.Y_NEGATIVE:
                return TemplateBorder.TOP
            case SpatialBlockBorder.Y_POSITIVE:
                return TemplateBorder.BOTTOM
            # add a wildcard pattern when function returns `None`
            # flagged by ty
            case _:
                raise ValueError(f"Cannot return the template border corresponding to {self} .")


class TemporalBlockBorder(Enum):
    """Enumerates the 2 different temporal borders for a block."""

    Z_NEGATIVE = SignedDirection3D(Direction3D.Z, False)
    Z_POSITIVE = SignedDirection3D(Direction3D.Z, True)


def border_from_signed_direction(
    direction: SignedDirection3D,
) -> SpatialBlockBorder | TemporalBlockBorder:
    """Get the block border from its direction.

    Args:
        direction: direction indicating the border to return.

    Returns:
        The border corresponding to the provided direction. Imagining a line
        starting from the block center and extending in the provided direction,
        the border pierced by the line is returned by this function.

        For example, if ``"+X"`` is provided, the returned border will be
        ``SpatialBlockBorder.X_POSITIVE``

    """
    match direction:
        case SignedDirection3D(Direction3D.Z, _):
            return TemporalBlockBorder(direction)
        case _:
            return SpatialBlockBorder(direction)
