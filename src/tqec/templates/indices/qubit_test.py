import numpy
import pytest

from tqec.exceptions import TQECWarning
from tqec.scale import LinearFunction, Scalable2D
from tqec.templates.indices.qubit import Qubit4WayJunctionTemplate, QubitTemplate


def test_creation() -> None:
    QubitTemplate()
    Qubit4WayJunctionTemplate()


def test_expected_plaquettes_number() -> None:
    assert QubitTemplate().expected_plaquettes_number == 14
    assert Qubit4WayJunctionTemplate().expected_plaquettes_number == 15


def test_scalable_shape() -> None:
    assert QubitTemplate().scalable_shape == Scalable2D(
        LinearFunction(2, 2), LinearFunction(2, 2)
    )
    assert Qubit4WayJunctionTemplate().scalable_shape == Scalable2D(
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


def test_qubit_4_way_junction_template_instantiation() -> None:
    template = Qubit4WayJunctionTemplate()

    expected_warning_message = (
        "Instantiating Qubit4WayJunctionTemplate with k=1. The "
        "instantiation array returned will not have any plaquette indexed "
        "9, which might break other parts of the library."
    )
    with pytest.warns(TQECWarning, match=expected_warning_message):
        numpy.testing.assert_array_equal(
            template.instantiate(1),
            [
                [1, 5, 6, 2],
                [7, 10, 11, 12],
                [8, 11, 10, 13],
                [3, 14, 15, 4],
            ],
        )
    numpy.testing.assert_array_equal(
        template.instantiate(2),
        [
            [1, 5, 6, 5, 6, 2],
            [7, 10, 11, 10, 11, 12],
            [8, 11, 10, 11, 9, 13],
            [7, 9, 11, 10, 11, 12],
            [8, 11, 10, 11, 10, 13],
            [3, 14, 15, 14, 15, 4],
        ],
    )
