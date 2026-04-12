from tqec.plaquette.constants import MEASUREMENT_SCHEDULE
from tqec.plaquette.rpng.translators.scheduled import ScheduledRPNGTranslator


class DefaultRPNGTranslator(ScheduledRPNGTranslator):
    """Default implementation of the RPNGTranslator interface.

    The plaquettes returned have the following properties:

    - the syndrome qubit is always reset in the ``X``-basis,
    - the syndrome qubit is always measured in the ``X``-basis,
    - the syndrome qubit is always the control of the 2-qubit gates used,
    - the 2-qubit gate used is always a ``Z``-controlled Pauli gate,
    - resets (and potentially hadamards) are always scheduled at timestep ``0``,
    - 2-qubit gates are always scheduled at timesteps in ``[1, 5]``,
    - measurements (and potentially hadamards) are always scheduled at timestep
      ``DefaultRPNGTranslator.MEASUREMENT_SCHEDULE`` that is currently equal to
      ``6``,
    - resets and measurements are always ordered from their basis (first ``X``,
      then ``Y``, and finally ``Z``),
    - hadamard gates are always after resets and measurements,
    - targets of reset, measurement and hadamard are always ordered.

    """

    MEASUREMENT_SCHEDULE = MEASUREMENT_SCHEDULE
