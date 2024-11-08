import pytest

from tqec.exceptions import TQECException
from tqec.interval import Interval
from tqec.position import Shape2D
from tqec.scale import LinearFunction, Scalable2D, round_or_fail


@pytest.mark.parametrize(
    "slope,offset", [(0, 0), (2, 0), (1, 0), (0, 4), (-1, 5), (2, -1)]
)
def test_linear_function(slope: int, offset: int) -> None:
    f = LinearFunction(slope, offset)
    assert f(10) == slope * 10 + offset
    assert f(1) == slope + offset
    assert f(0) == offset
    assert f(-4) == slope * -4 + offset


def test_linear_function_operators() -> None:
    a, b = LinearFunction(2, 5), LinearFunction(3, 1)
    assert (a + b)(10) == a(10) + b(10)
    assert (a - b)(3) == a(3) - b(3)
    assert (a + 3)(10) == a(10) + 3
    assert (a - 3)(3) == a(3) - 3
    assert (3 * a)(54) == 3 * a(54)
    assert (a * 3)(54) == 3 * a(54)


def test_intersection() -> None:
    a, b = LinearFunction(2, 5), LinearFunction(3, 1)
    intersection = a.intersection(b)
    assert intersection is not None
    assert abs(intersection - 4) < 1e-8

    intersection = a.intersection(a)
    assert intersection is None


def test_linear_function_comparison() -> None:
    a, b = LinearFunction(2, 5), LinearFunction(3, 1)

    assert (a < b) == Interval(
        4.0, float("inf"), start_excluded=True, end_excluded=True
    )
    assert (b < a) == Interval(
        float("-inf"), 4.0, start_excluded=True, end_excluded=True
    )
    assert (a < a).is_empty()
    assert (a <= b) == Interval(
        4.0, float("inf"), start_excluded=False, end_excluded=True
    )
    assert (a <= a) == Interval(
        float("-inf"), float("inf"), start_excluded=True, end_excluded=True
    )


def test_scalable_2d_creation() -> None:
    Scalable2D(LinearFunction(0, 0), LinearFunction(1, 0))
    Scalable2D(LinearFunction(-1903, 23), LinearFunction(0, -10932784))


def test_scalable_2d_shape() -> None:
    scalable = Scalable2D(LinearFunction(0, 0), LinearFunction(1, 0))
    assert scalable.to_numpy_shape(2) == (2, 0)
    assert scalable.to_numpy_shape(234) == (234, 0)
    assert scalable.to_shape_2d(7) == Shape2D(0, 7)


def test_scalable_2d_add() -> None:
    A = Scalable2D(LinearFunction(0, 0), LinearFunction(1, 0))
    B = Scalable2D(LinearFunction(-12, 0), LinearFunction(1, 5))
    C = Scalable2D(LinearFunction(-12, 0), LinearFunction(2, 5))
    assert A + B == C
    with pytest.raises(TQECException):
        A + LinearFunction(1, 0)  # type: ignore


def test_round_or_fail() -> None:
    round_or_fail(1.0)
    round_or_fail(0.0)
    round_or_fail(-13.0)
    with pytest.raises(TQECException, match=r"^Rounding from 3.1 to integer failed.$"):
        round_or_fail(3.1)
