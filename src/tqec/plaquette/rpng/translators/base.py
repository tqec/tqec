from abc import ABC, abstractmethod

from tqec.plaquette.plaquette import Plaquette
from tqec.plaquette.rpng import RPNGDescription


class RPNGTranslator(ABC):
    """Base interface for classes capable of generating a
    :class:`~tqec.plaquette.plaquette.Plaquette` instance from a
    :class:`~tqec.plaquette.rpng.RPNGDescription` instance.
    """

    @abstractmethod
    def translate(
        self,
        rpng_description: RPNGDescription,
    ) -> Plaquette:
        """Generate the plaquette corresponding to the provided ``RPNG``
        description.

        Args:
            rpng_description: description of the plaquette to generate.

        Returns:
            a valid implementation of the provided
            :class:`~tqec.plaquette.rpng.RPNGDescription` instance.
        """
        pass
