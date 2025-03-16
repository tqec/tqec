from tqec.compile.blocks.enums import (
    SpatialBlockBorder,
    TemporalBlockBorder,
    border_from_signed_direction,
)
from tqec.templates.enums import TemplateBorder
from tqec.utils.position import Direction3D, SignedDirection3D


def test_border_from_signed_direction() -> None:
    for direction in Direction3D:
        for signedness in [False, True]:
            sdir = SignedDirection3D(direction, signedness)
            border = border_from_signed_direction(sdir)
            if direction == Direction3D.Z:
                assert isinstance(border, TemporalBlockBorder)
            else:
                assert isinstance(border, SpatialBlockBorder)
            assert border.value == sdir


def test_to_template_border() -> None:
    assert SpatialBlockBorder.X_POSITIVE.to_template_border() == TemplateBorder.RIGHT
    assert SpatialBlockBorder.X_NEGATIVE.to_template_border() == TemplateBorder.LEFT
    assert SpatialBlockBorder.Y_POSITIVE.to_template_border() == TemplateBorder.BOTTOM
    assert SpatialBlockBorder.Y_NEGATIVE.to_template_border() == TemplateBorder.TOP
