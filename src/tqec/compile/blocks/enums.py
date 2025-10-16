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


class Alignment(Enum):
    """Specifies temporal alignment for injected blocks relative to surrounding computation.

    When an :class:`~tqec.compile.blocks.block.InjectedBlock` is woven into a
    layer-generated circuit, its alignment determines how its timesteps align with
    the tree-generated timesteps.

    Attributes:
        HEAD: The injected block's first timestep immediately follows the last
            timestep of the preceding block. Used when the injection must observe
            stabilizers from the previous layer and create new stabilizers for the
            current layer. Flow termination happens at the end of the previous slice,
            and flow creation happens at the start of the current slice.

        TAIL: The injected block's last timestep immediately precedes the first
            timestep of the following block. Used when the injection must observe
            stabilizers from the current layer and create new stabilizers for the
            next layer. Flow termination happens at the end of the current slice,
            and flow creation happens at the start of the next slice.

    See Also:
        - :class:`~tqec.compile.blocks.block.InjectedBlock` for usage context
        - :class:`~tqec.compile.tree.injection.InjectionBuilder` for implementation details

    """

    HEAD = "head"
    TAIL = "tail"
