import pytest

from tqec.utils.exceptions import TQECException
from tqec.utils.position import Shape2D
from tqec.utils.scale import LinearFunction, Scalable2D, round_or_fail


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


def test_round_or_fail() -> None:
    round_or_fail(1.0)
    round_or_fail(0.0)
    round_or_fail(-13.0)
    with pytest.raises(TQECException, match=r"^Rounding from 3.1 to integer failed.$"):
        round_or_fail(3.1)


def test_integer_eval() -> None:
    a, b = LinearFunction(2, 5), LinearFunction(-3, 1)
    assert a.integer_eval(5) == 2 * 5 + 5
    assert b.integer_eval(3) == -3 * 3 + 1


def test_exact_integer_div() -> None:
    a, b, c = LinearFunction(2, 4), LinearFunction(0, 6), LinearFunction(1, 3)
    assert a.exact_integer_div(1) == a
    assert a.exact_integer_div(-1) == LinearFunction(-a.slope, -a.offset)
    assert b.exact_integer_div(1) == b
    assert c.exact_integer_div(1) == c
    assert a.exact_integer_div(2) == LinearFunction(1, 2)
    assert b.exact_integer_div(2) == LinearFunction(0, 3)
    assert b.exact_integer_div(3) == LinearFunction(0, 2)
    assert b.exact_integer_div(-3) == LinearFunction(0, -2)
    assert b.exact_integer_div(6) == LinearFunction(0, 1)
    with pytest.raises(TQECException):
        b.exact_integer_div(5)
    with pytest.raises(TQECException):
        a.exact_integer_div(3)
    with pytest.raises(ZeroDivisionError):
        a.exact_integer_div(0)


def test_is_constant() -> None:
    assert LinearFunction(0, 0).is_constant()
    assert LinearFunction(0, 3).is_constant()
    assert LinearFunction(0, -5).is_constant()
    assert not LinearFunction(1, 0).is_constant()
    assert not LinearFunction(-6, 6).is_constant()


def test_is_scalable() -> None:
    assert not LinearFunction(0, 0).is_scalable()
    assert not LinearFunction(0, 3).is_scalable()
    assert not LinearFunction(0, -5).is_scalable()
    assert LinearFunction(1, 0).is_scalable()
    assert LinearFunction(-6, 6).is_scalable()


def test_is_close_to() -> None:
    assert not LinearFunction(0, 0).is_close_to(LinearFunction(0, 1))
    assert not LinearFunction(0, 0).is_close_to(LinearFunction(1, 0))
    assert LinearFunction(0, 0).is_close_to(LinearFunction(0, 0))
    assert LinearFunction(0, 0).is_close_to(LinearFunction(0, -0))
