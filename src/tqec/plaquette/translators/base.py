from abc import ABC, abstractmethod

from tqec.plaquette.plaquette import Plaquette
from tqec.plaquette.qubit import PlaquetteQubits, SquarePlaquetteQubits
from tqec.plaquette.rpng import RPNGDescription


class RPNGTranslator(ABC):
    @abstractmethod
    def translate(
        self,
        rpng_description: RPNGDescription,
        measurement_schedule: int,
        qubits: PlaquetteQubits = SquarePlaquetteQubits(),
    ) -> Plaquette:
        pass
