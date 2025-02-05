from random import randint

import pytest

from tqec.utils.maths import least_common_multiple, prime_factors, product


def test_prime_factorisation() -> None:
    assert prime_factors(0) == []
    assert prime_factors(1) == []
    assert prime_factors(2) == [2]
    assert prime_factors(3) == [3]
    assert prime_factors(4) == [2, 2]
    assert prime_factors(5) == [5]


@pytest.mark.parametrize("number", [randint(1, 2**20) for _ in range(100)])
def test_prime_factorisation_random(number: int) -> None:
    assert product(prime_factors(number)) == number


def test_lcm() -> None:
    assert least_common_multiple([]) == 1
    assert least_common_multiple([3]) == 3
    assert least_common_multiple([2, 2]) == 2
    # Hard-coded from https://en.wikipedia.org/wiki/Least_common_multiple#Calculation
    assert least_common_multiple([2, 7]) == 14
    assert least_common_multiple([2, 5, 3]) == 30
    assert least_common_multiple([2, 3, 4]) == 12
    assert least_common_multiple([3, 4, 5]) == 60
    assert least_common_multiple([7, 5, 4, 3, 2]) == 420
    assert least_common_multiple([8, 9, 21]) == 504


@pytest.mark.parametrize(
    "numbers", [[randint(1, 2**20) for _ in range(10)] for _ in range(100)]
)
def test_lcm_random(numbers: list[int]) -> None:
    lcm = least_common_multiple(numbers)
    for n in numbers:
        assert lcm % n == 0
