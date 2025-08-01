import numpy

from tqec.templates._testing import FixedTemplate
from tqec.utils.position import PlaquetteShape2D
from tqec.utils.scale import LinearFunction, PlaquetteScalable2D


def test_construction() -> None:
    FixedTemplate([[0]])
    FixedTemplate([[1]])
    FixedTemplate(((1,),))
    FixedTemplate([[]])


def test_instantiation() -> None:
    numpy.testing.assert_array_equal(FixedTemplate([[0]]).instantiate(plaquette_indices=[1]), [[1]])
    numpy.testing.assert_array_equal(FixedTemplate([[0]]).instantiate(), [[1]])
    numpy.testing.assert_array_equal(
        FixedTemplate([[1]]).instantiate(plaquette_indices=[1, 2]), [[2]]
    )
    numpy.testing.assert_array_equal(
        FixedTemplate([[0, 1], [1, 2]]).instantiate(plaquette_indices=[1, 2, 3]),
        [[1, 2], [2, 3]],
    )


def test_shape() -> None:
    assert FixedTemplate([[0]]).scalable_shape == PlaquetteScalable2D(
        LinearFunction(0, 1), LinearFunction(0, 1)
    )
    assert FixedTemplate([[0]]).shape(1) == PlaquetteShape2D(1, 1)


def test_number_of_expected_plaquettes() -> None:
    for i in range(10):
        assert FixedTemplate([[i]]).expected_plaquettes_number == i + 1
        assert FixedTemplate([[0, 3], [i, i]]).expected_plaquettes_number == max(i + 1, 3 + 1)
