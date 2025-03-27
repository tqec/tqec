import numpy
import pytest

from tqec.templates.enums import TemplateBorder
from tqec.templates.qubit import (
    QubitHorizontalBorders,
    QubitSpatialCubeTemplate,
    QubitTemplate,
    QubitVerticalBorders,
)
from tqec.utils.exceptions import TQECException
from tqec.utils.scale import LinearFunction, PlaquetteScalable2D


def test_creation() -> None:
    QubitTemplate()
    QubitHorizontalBorders()
    QubitVerticalBorders()
    QubitSpatialCubeTemplate()


def test_expected_plaquettes_number() -> None:
    assert QubitTemplate().expected_plaquettes_number == 14
    assert QubitHorizontalBorders().expected_plaquettes_number == 8
    assert QubitVerticalBorders().expected_plaquettes_number == 8
    assert QubitSpatialCubeTemplate().expected_plaquettes_number == 21


def test_scalable_shape() -> None:
    assert QubitTemplate().scalable_shape == PlaquetteScalable2D(
        LinearFunction(2, 2), LinearFunction(2, 2)
    )
    assert QubitHorizontalBorders().scalable_shape == PlaquetteScalable2D(
        LinearFunction(2, 2), LinearFunction(0, 2)
    )
    assert QubitVerticalBorders().scalable_shape == PlaquetteScalable2D(
        LinearFunction(0, 2), LinearFunction(2, 2)
    )
    assert QubitSpatialCubeTemplate().scalable_shape == PlaquetteScalable2D(
        LinearFunction(2, 2), LinearFunction(2, 2)
    )


def test_qubit_template_instantiation() -> None:
    template = QubitTemplate()
    numpy.testing.assert_array_equal(
        template.instantiate(2),
        [
            [1, 5, 6, 5, 6, 2],
            [7, 9, 10, 9, 10, 11],
            [8, 10, 9, 10, 9, 12],
            [7, 9, 10, 9, 10, 11],
            [8, 10, 9, 10, 9, 12],
            [3, 13, 14, 13, 14, 4],
        ],
    )
    numpy.testing.assert_array_equal(
        template.instantiate(4),
        [
            [1, 5, 6, 5, 6, 5, 6, 5, 6, 2],
            [7, 9, 10, 9, 10, 9, 10, 9, 10, 11],
            [8, 10, 9, 10, 9, 10, 9, 10, 9, 12],
            [7, 9, 10, 9, 10, 9, 10, 9, 10, 11],
            [8, 10, 9, 10, 9, 10, 9, 10, 9, 12],
            [7, 9, 10, 9, 10, 9, 10, 9, 10, 11],
            [8, 10, 9, 10, 9, 10, 9, 10, 9, 12],
            [7, 9, 10, 9, 10, 9, 10, 9, 10, 11],
            [8, 10, 9, 10, 9, 10, 9, 10, 9, 12],
            [3, 13, 14, 13, 14, 13, 14, 13, 14, 4],
        ],
    )


def test_qubit_template_borders_indices() -> None:
    template = QubitTemplate()
    instantiation = template.instantiate(2)

    assert list(template.get_border_indices(TemplateBorder.TOP)) == [
        instantiation[0][i] for i in [0, 1, 2, -1]
    ]
    assert list(template.get_border_indices(TemplateBorder.BOTTOM)) == [
        instantiation[-1][i] for i in [0, 1, 2, -1]
    ]
    assert list(template.get_border_indices(TemplateBorder.LEFT)) == [
        instantiation[i][0] for i in [0, 1, 2, -1]
    ]
    assert list(template.get_border_indices(TemplateBorder.RIGHT)) == [
        instantiation[i][-1] for i in [0, 1, 2, -1]
    ]


def test_qubit_horizontal_borders_template_instantiation() -> None:
    template = QubitHorizontalBorders()
    numpy.testing.assert_array_equal(
        template.instantiate(2),
        [
            [1, 5, 6, 5, 6, 2],
            [3, 7, 8, 7, 8, 4],
        ],
    )
    numpy.testing.assert_array_equal(
        template.instantiate(4),
        [
            [1, 5, 6, 5, 6, 5, 6, 5, 6, 2],
            [3, 7, 8, 7, 8, 7, 8, 7, 8, 4],
        ],
    )


def test_horizontal_borders_template_borders_indices() -> None:
    template = QubitHorizontalBorders()
    instantiation = template.instantiate(2)

    expected_error_message = (
        "Template QubitHorizontalBorders does not have repeating elements "
        "on the {} border."
    )
    with pytest.raises(TQECException, match=expected_error_message.format("LEFT")):
        template.get_border_indices(TemplateBorder.LEFT)
    with pytest.raises(TQECException, match=expected_error_message.format("RIGHT")):
        template.get_border_indices(TemplateBorder.RIGHT)
    assert list(template.get_border_indices(TemplateBorder.TOP)) == [
        instantiation[0][i] for i in [0, 1, 2, -1]
    ]
    assert list(template.get_border_indices(TemplateBorder.BOTTOM)) == [
        instantiation[1][i] for i in [0, 1, 2, -1]
    ]


def test_qubit_vertical_borders_template_instantiation() -> None:
    template = QubitVerticalBorders()
    numpy.testing.assert_array_equal(
        template.instantiate(2),
        [
            [1, 2],
            [5, 7],
            [6, 8],
            [5, 7],
            [6, 8],
            [3, 4],
        ],
    )
    numpy.testing.assert_array_equal(
        template.instantiate(4),
        [
            [1, 2],
            [5, 7],
            [6, 8],
            [5, 7],
            [6, 8],
            [5, 7],
            [6, 8],
            [5, 7],
            [6, 8],
            [3, 4],
        ],
    )


def test_vertical_borders_template_borders_indices() -> None:
    template = QubitVerticalBorders()
    instantiation = template.instantiate(2)

    expected_error_message = (
        "Template QubitVerticalBorders does not have repeating elements "
        "on the {} border."
    )
    with pytest.raises(TQECException, match=expected_error_message.format("TOP")):
        template.get_border_indices(TemplateBorder.TOP)
    with pytest.raises(TQECException, match=expected_error_message.format("BOTTOM")):
        template.get_border_indices(TemplateBorder.BOTTOM)
    assert list(template.get_border_indices(TemplateBorder.LEFT)) == [
        instantiation[i][0] for i in [0, 1, 2, -1]
    ]
    assert list(template.get_border_indices(TemplateBorder.RIGHT)) == [
        instantiation[i][1] for i in [0, 1, 2, -1]
    ]


def test_qubit_spatial_cube_template_instantiation() -> None:
    template = QubitSpatialCubeTemplate()

    numpy.testing.assert_array_equal(
        template.instantiate(1),
        [
            [1, 9, 10, 2],
            [11, 5, 6, 18],
            [12, 7, 8, 19],
            [3, 20, 21, 4],
        ],
    )
    numpy.testing.assert_array_equal(
        template.instantiate(2),
        [
            [1, 9, 10, 9, 10, 2],
            [11, 5, 17, 13, 6, 18],
            [12, 17, 13, 17, 14, 19],
            [11, 16, 17, 15, 17, 18],
            [12, 7, 15, 17, 8, 19],
            [3, 20, 21, 20, 21, 4],
        ],
    )


def test_qubit_spatial_cube_template_borders_indices() -> None:
    template = QubitSpatialCubeTemplate()
    instantiation = template.instantiate(2)

    assert list(template.get_border_indices(TemplateBorder.TOP)) == [
        instantiation[0][i] for i in [0, 1, 2, -1]
    ]
    assert list(template.get_border_indices(TemplateBorder.BOTTOM)) == [
        instantiation[-1][i] for i in [0, 1, 2, -1]
    ]
    assert list(template.get_border_indices(TemplateBorder.LEFT)) == [
        instantiation[i][0] for i in [0, 1, 2, -1]
    ]
    assert list(template.get_border_indices(TemplateBorder.RIGHT)) == [
        instantiation[i][-1] for i in [0, 1, 2, -1]
    ]
