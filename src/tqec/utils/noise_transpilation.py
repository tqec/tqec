"""Rewrite circuits into the Z-basis interaction gate set used by the SI1000 noise model."""

import stim


def transpile_to_si1000_gateset(circuit: stim.Circuit) -> stim.Circuit:
    """Rewrite ``circuit`` into the Z-basis gate set that ``NoiseModel.si1000`` supports.

    ``NoiseModel.si1000`` only defines noise rules for Z-basis resets and measurements (``R`` /
    ``M``) and raises on non-Z collapses such as ``RX`` / ``MX`` / ``RY`` / ``MY``. Y-basis
    circuits (for example Y half cube circuits) therefore cannot be given SI1000 noise directly,
    and must first be rewritten into a stabilizer-equivalent Z-basis interaction circuit.

    Args:
        circuit: The circuit to rewrite.

    Returns:
        A stabilizer-equivalent circuit expressed in the Z-basis interaction gate set.

    Raises:
        NotImplementedError

    """
    raise NotImplementedError("SI1000 gate-set transpilation is not implemented yet.")
