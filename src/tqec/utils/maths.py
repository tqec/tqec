from collections import Counter
from itertools import chain
from typing import Sequence


def product(numbers: Sequence[int]) -> int:
    ret = 1
    for n in numbers:
        ret *= n
    return ret


def prime_factors(number: int) -> list[int]:
    """Unoptimized prime factor computation."""
    i = 2
    factors = []
    while i * i <= number:
        if number % i:
            i += 1
        else:
            number //= i
            factors.append(i)
    if number > 1:
        factors.append(number)
    return factors


def least_common_multiple(numbers: Sequence[int]) -> int:
    factorisations = [Counter(prime_factors(n)) for n in numbers]
    factors: frozenset[int] = frozenset(
        chain.from_iterable(counter.keys() for counter in factorisations)
    )
    ret = 1
    for f in factors:
        ret *= f ** max(factorisation.get(f, 0) for factorisation in factorisations)
    return ret
