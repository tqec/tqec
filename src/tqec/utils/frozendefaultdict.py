from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from copy import deepcopy
from typing import Generic, TypeVar, cast

from typing_extensions import override

K = TypeVar("K")
V = TypeVar("V")
Vp = TypeVar("Vp")


class FrozenDefaultDict(Generic[K, V], Mapping[K, V]):
    def __init__(
        self,
        arg: Mapping[K, V] | Iterable[tuple[K, V]] | None = None,
        *,
        default_value: V | None = None,
    ) -> None:
        """Implement a ``defaultdict`` that cannot be mutated.

        This class re-defines all the mutating methods of `defaultdict` (i.e., all
        the mutating methods of `dict` and `__missing__`) in order to make any
        instance immutable.

        Note on re-defining `__missing__`:

        The standard `defaultdict` implementation is entirely based on the
        `__missing__` method (described here
        https://docs.python.org/3/library/collections.html#collections.defaultdict.__missing__)
        that is called when a user-provided key was not found in the defined keys.
        This `__missing__` method try to use `self.default_factory` to create a new
        value and inserts that new value in the dictionary. That last part is
        problematic for :class:`Plaquettes` and in particular to compare collections
        of :class:`Plaquettes` through `__hash__` and `__eq__`.

        Args:
            arg: a mapping from defined keys to values. Any key that is not present will be
                implicitly associated to the provided ``default_value``.
            default_value: value that will be returned (without copying) when a key not present in
                ``arg`` is queried.

        """
        super().__init__()
        self._dict: dict[K, V] = dict(arg) if arg is not None else dict()
        self._default_value = default_value

    def __missing__(self, key: K) -> V:
        if self._default_value is None:
            raise KeyError(key)
        return self._default_value

    @override
    def __getitem__(self, key: K) -> V:
        try:
            return self._dict[key]
        except KeyError:
            return self.__missing__(key)

    @override
    def __iter__(self) -> Iterator[K]:
        return iter(self._dict)

    @override
    def __len__(self) -> int:
        return len(self._dict)  # pragma: no cover

    @override
    def __contains__(self, key: object) -> bool:
        return self._dict.__contains__(key)

    def __or__(self, other: Mapping[K, V]) -> FrozenDefaultDict[K, V]:
        mapping = deepcopy(self._dict)
        mapping.update(other)
        return FrozenDefaultDict(mapping, default_value=self._default_value)

    def __hash__(self) -> int:
        return hash(tuple(sorted(self.items())))  # pragma: no cover

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FrozenDefaultDict):
            return False  # pragma: no cover
        other = cast(FrozenDefaultDict[K, V], other)
        return (self._default_value == other._default_value) and self._dict == other._dict

    def has_default_value(self) -> bool:
        """Return ``True`` if ``self`` has a default value."""
        return self._default_value is not None  # pragma: no cover

    @property
    def default_value(self) -> V | None:
        """Get the default value returned when a queried key is missing."""
        return self._default_value

    def map_keys(self, callable: Callable[[K], K]) -> FrozenDefaultDict[K, V]:
        """Apply ``callable`` to each key and return a new instance with the modified keys."""
        return FrozenDefaultDict(
            {callable(k): v for k, v in self.items()},
            default_value=self._default_value,
        )

    def map_values(self, callable: Callable[[V], Vp]) -> FrozenDefaultDict[K, Vp]:
        """Apply ``callable`` to each value and return a new instance with the modified values."""
        default_value: Vp | None = None
        if self.default_value is not None:
            default_value = callable(self.default_value)
        defined_type: dict[K, Vp] = {k: callable(v) for k, v in self.items()}
        return cast(
            FrozenDefaultDict[K, Vp], FrozenDefaultDict(defined_type, default_value=default_value)
        )

    def map_keys_if_present(self, mapping: Mapping[K, K]) -> FrozenDefaultDict[K, V]:
        """Apply ``callable`` to each key and return a new instance with the modified keys."""
        return FrozenDefaultDict(  # pragma: no cover
            {mapping[k]: v for k, v in self.items() if k in mapping},
            default_value=self._default_value,
        )
