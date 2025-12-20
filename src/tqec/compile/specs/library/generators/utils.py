"""Provides utility code to help building generators.

The main utility provided by this module at the moment is
:class:`PlaquetteMapper` that is a "Funcorator" (a "functor", i.e., a callable
object that may have a state, and a "decorator") that can be used to define
functions that return :class:`~tqec.plaquettes.plaquettes.Plaquettes` instances
from one that returns `FrozenDefaultDict[int, RPNGDescription]`.

"""

from collections.abc import Callable
from functools import wraps
from types import FunctionType
from typing import Final, ParamSpec, cast

from tqec.plaquette.compilation.base import IdentityPlaquetteCompiler, PlaquetteCompiler
from tqec.plaquette.plaquette import Plaquette, Plaquettes
from tqec.plaquette.rpng.rpng import RPNGDescription
from tqec.plaquette.rpng.translators.base import RPNGTranslator
from tqec.plaquette.rpng.translators.default import DefaultRPNGTranslator
from tqec.utils.exceptions import TQECError
from tqec.utils.frozendefaultdict import FrozenDefaultDict

P = ParamSpec("P")


class PlaquetteMapper:
    def __init__(
        self,
        translator: RPNGTranslator = DefaultRPNGTranslator(),
        compiler: PlaquetteCompiler = IdentityPlaquetteCompiler,
    ) -> None:
        """Wrap a translator and a compiler to ease plaquette generation."""
        self._translator = translator
        self._compiler = compiler

    def get_plaquette(self, description: RPNGDescription) -> Plaquette:
        """Successively call the translator and the compiler to return a plaquette."""
        return self._compiler.compile(self._translator.translate(description))

    def __call__(
        self,
        f: Callable[P, FrozenDefaultDict[int, RPNGDescription]],
    ) -> Callable[P, Plaquettes]:
        """Wrap the provided callable ``f`` to automatically get :class:`.Plaquette` instances.

        This method wraps correctly the provided function such that :meth:`get_plaquette` is called
        on each of the returned :class:`.RPNGDescription` instance to get its corresponding
        :class:`.Plaquette`.

        """
        func = cast(FunctionType, f)

        # The wraps decorator make sure that the original function name, module,
        # docstring, ... is correctly transmitted to the wrapper.
        @wraps(f)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Plaquettes:
            return Plaquettes(f(*args, **kwargs).map_values(self.get_plaquette))

        # Because the function name have to change, we need to explicitly change
        # it here.
        wrapped_func_name = func.__name__
        expected_end = "_rpng_descriptions"
        if not wrapped_func_name.endswith(expected_end):
            raise TQECError(
                f"Cannot wrap function {func.__module__}.{func.__name__}: its name "
                f"does not end with '{expected_end}'."
            )
        wrapped_name = wrapped_func_name[: -len(expected_end)] + "_plaquettes"
        wrapper.__name__ = wrapped_name
        # Return the final function.
        return wrapper


default_plaquette_mapper: Final = PlaquetteMapper()
