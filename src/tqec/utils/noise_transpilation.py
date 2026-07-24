"""Rewrite circuits into the Z-basis interaction gate set used by the SI1000 noise model."""

import stim
from stimflow import transpile_to_z_basis_interaction_circuit


def transpile_to_si1000_gateset(circuit: stim.Circuit) -> stim.Circuit:
    """Rewrite ``circuit`` into the Z-basis gate set that ``NoiseModel.si1000`` supports.

    ``NoiseModel.si1000`` only defines noise rules for Z-basis resets and measurements (``R`` /
    ``M``) and raises on non-Z collapses such as ``RX`` / ``MX`` / ``RY`` / ``MY``. Y-basis
    circuits (for example Y half cube circuits) therefore cannot be given SI1000 noise directly.

    This helper returns a stabilizer-equivalent circuit that uses only Z-basis resets and
    measurements together with single-qubit rotations and ``CZ`` / ``ISWAP`` interactions, so
    ``NoiseModel.si1000`` can be applied to it. Non-Z collapses are moved into the Z basis by
    inserting the appropriate single-qubit rotations before/after them, and controlled Pauli
    interactions are rewritten as ``CZ`` sandwiched between rotations. Detector and observable
    annotations, and the measurement-record ordering they reference, are preserved.

    The transpilation engine is ``stimflow.transpile_to_z_basis_interaction_circuit`` from the
    ``stimflow`` package (the Apache-2.0 ``glue/stimflow`` component shipped with Stim), which is
    a declared dependency of ``tqec``.

    Args:
        circuit: The circuit to rewrite. May contain resets, measurements and interactions in
            any Pauli basis, as well as ``DETECTOR`` / ``OBSERVABLE_INCLUDE`` annotations.

    Returns:
        A stabilizer-equivalent circuit expressed in the Z-basis interaction gate set.

    """
    return transpile_to_z_basis_interaction_circuit(circuit)
