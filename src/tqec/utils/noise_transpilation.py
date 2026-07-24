"""Rewrite circuits into the Z-basis interaction gate set used by the SI1000 noise model.

The SI1000 gate-set transpilation is **not yet implemented on this branch**. A working
implementation -- delegating to ``stimflow.transpile_to_z_basis_interaction_circuit`` -- lives on
the ``kd/si1000-transpilation`` branch, which carries the corresponding ``stimflow`` dependency.
It was moved off ``kd/dae-batch-processing`` so this branch does not pull in a git-subdirectory
dependency on an unreleased Stim fork sub-package. See the module attribution pattern in
``tqec.utils.noise_model`` for how a future vendored copy of the transpiler would be credited.
"""

import stim


def transpile_to_si1000_gateset(circuit: stim.Circuit) -> stim.Circuit:
    """Rewrite ``circuit`` into the Z-basis gate set that ``NoiseModel.si1000`` supports.

    ``NoiseModel.si1000`` only defines noise rules for Z-basis resets and measurements (``R`` /
    ``M``) and raises on non-Z collapses such as ``RX`` / ``MX`` / ``RY`` / ``MY``. Y-basis
    circuits (for example Y half cube circuits) therefore cannot be given SI1000 noise directly,
    and must first be rewritten into a stabilizer-equivalent Z-basis interaction circuit.

    This transpilation is not implemented on this branch. The working implementation lives on the
    ``kd/si1000-transpilation`` branch, where it delegates to
    ``stimflow.transpile_to_z_basis_interaction_circuit``. Until that work lands here, any
    simulation path that requests the ``si1000`` noise model on a non-Z-basis circuit fails
    loudly rather than producing a silently wrong result.

    Args:
        circuit: The circuit to rewrite.

    Returns:
        A stabilizer-equivalent circuit expressed in the Z-basis interaction gate set.

    Raises:
        NotImplementedError: Always, on this branch. SI1000 gate-set transpilation has not yet
            been implemented here; use the ``kd/si1000-transpilation`` branch.

    """
    raise NotImplementedError(
        "SI1000 gate-set transpilation is not implemented on this branch. The working "
        "implementation (delegating to stimflow) lives on the 'kd/si1000-transpilation' branch; "
        "it was moved off 'kd/dae-batch-processing' to drop the stimflow git-subdirectory "
        "dependency."
    )
