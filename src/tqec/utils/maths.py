from collections import Counter
from itertools import chain
from typing import Sequence


def product(numbers: Sequence[int]) -> int:
    """Returns the product of the provided numbers."""
    ret = 1
    for n in numbers:
        ret *= n
    return ret


def prime_factors(n: int) -> list[int]:
    """Unoptimized prime factor computation.

    Args:
        n: number to find the prime factors of.

    Returns:
        a list of the prime factors of the provided ``n``.
    """
    i = 2
    factors = []
    while i * i <= n:
        if n % i:
            i += 1
        else:
            n //= i
            factors.append(i)
    if n > 1:
        factors.append(n)
    return factors


def least_common_multiple(numbers: Sequence[int]) -> int:
    """Returns the least common multiple of the provided numbers.

    This function returns a number ``n`` such that for all ``k`` in the provided
    ``numbers``, ``n`` is a multiple of ``k``.

    Args:
        numbers: numbers to find the least common multiple of.

    Returns:
        a number ``n`` such that for all ``k`` in the provided ``numbers``,
        ``n`` is a multiple of ``k``.
    """
    factorisations = [Counter(prime_factors(n)) for n in numbers]
    factors: frozenset[int] = frozenset(
        chain.from_iterable(counter.keys() for counter in factorisations)
    )
    ret = 1
    for f in factors:
        ret *= f ** max(factorisation.get(f, 0) for factorisation in factorisations)
    return ret
