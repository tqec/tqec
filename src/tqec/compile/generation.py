"""Defines :meth:`.generate_circuit`, one of the core method of the :mod:`tqec` package.

This module defines two of core methods of the :mod:`tqec` package:

- :meth:`generate_circuit` that is the most convenient method for external users.
- :meth:`generate_circuit_from_instantiation` that gives more freedom to the
  user (and is used internally by :meth:`generate_circuit`) at the expense of
  often less convenient inputs.

Both of these methods are used to generate the ``stim.Circuit`` instance
representing **one** time slice (often equivalent to "one QEC round"). Users are
expected to call these methods several times and concatenate the output
``stim.Circuit`` instances in time to obtain a full QEC implementation.

Note that these methods do not work with ``REPEAT`` instructions.

"""

from __future__ import annotations

import numpy
import numpy.typing as npt

from tqec.circuit.schedule import (
    ScheduledCircuit,
    merge_scheduled_circuits,
    relabel_circuits_qubit_indices,
)
from tqec.plaquette.plaquette import Plaquettes
from tqec.templates.base import Template
from tqec.utils.array import to2dlist
from tqec.utils.position import Shift2D


def generate_circuit(template: Template, k: int, plaquettes: Plaquettes) -> ScheduledCircuit:
    """Generate a quantum circuit from a template and its plaquettes.

    This is one of the core methods of the :mod:`tqec` package. It generates a
    quantum circuit from the description of the template that should be
    implemented as well as the plaquettes that should be used to instantiate the
    provided template.

    This function requires that a few pre-conditions on the inputs are met:

    1. the number of plaquettes provided should match the number of plaquettes
       required by the provided template.
    2. all the provided plaquettes should be implemented on
       :class:`~.qubit.GridQubit` instances **only**.

    If any of the above pre-conditions is not met, the inputs are considered
    invalid, in which case this function **might** raise an error.

    Args:
        template: spatial description of the quantum error correction experiment
            we want to implement.
        k: scaling parameter used to instantiate the provided ``template``.
        plaquettes: description of the computation that should happen at
            different time-slices of the quantum error correction experiment (or
            at least part of it).

    Returns:
        a :class:`~.schedule.circuit.ScheduledCircuit` instance implementing the
        (part of) quantum error correction experiment represented by the
        provided inputs.

    """
    # instantiate the template with the appropriate plaquette indices.
    # Index 0 is "no plaquette" by convention and should not be included here.
    _indices = list(range(1, template.expected_plaquettes_number + 1))
    template_plaquettes = template.instantiate(k, _indices)
    increments = template.get_increments()

    return generate_circuit_from_instantiation(template_plaquettes, plaquettes, increments)


def generate_circuit_from_instantiation(
    plaquette_array: npt.NDArray[numpy.int_],
    plaquettes: Plaquettes,
    increments: Shift2D,
) -> ScheduledCircuit:
    """Generate a quantum circuit from an array of plaquette indices and the associated plaquettes.

    This is one of the core methods of the :mod:`tqec` package. It generates a
    quantum circuit from a spatial description of where the plaquettes should be
    located as well as the actual plaquettes used.

    This function requires that a few pre-conditions on the inputs are met:

    1. the number of plaquettes provided should match the number of plaquettes
       required by the provided template.
    2. all the provided plaquettes should be implemented on
       :class:`~.qubit.GridQubit` instances **only**.

    If any of the above pre-conditions is not met, the inputs are considered
    invalid, in which case this function **might** raise an error.

    Args:
        plaquette_array: a 2-dimensional array of indices referencing
            :class:`~tqec.plaquette.plaquette.Plaquette` instances in the
            ``plaquettes`` argument.
        plaquettes: description of the computation that should happen at
            different time-slices of the quantum error correction experiment (or
            at least part of it).
        increments: the displacement between each plaquette origin.

    Returns:
        a :class:`~.schedule.circuit.ScheduledCircuit` instance implementing the
        (part of) quantum error correction experiment represented by the
        provided inputs.

    Raises:
        TQECError: if any index in ``plaquette_array`` is not correctly
            associated to a plaquette in ``plaquettes``.

    """
    # Collect all the used plaquette indices, removing 0 if present.
    indices = numpy.unique(plaquette_array)
    if indices[0] == 0:
        indices = indices[1:]

    # Plaquettes indices are starting at 1 in template_plaquettes. To avoid
    # offsets in the following code, we add an empty circuit at position 0.
    plaquette_circuits = {0: ScheduledCircuit.empty()} | {i: plaquettes[i].circuit for i in indices}

    # Generate the ScheduledCircuit instances for each plaquette instantiation
    all_scheduled_circuits: list[ScheduledCircuit] = []
    additional_mergeable_instructions: set[str] = set()
    # The below line is not strictly needed, but makes type checkers happy with
    # type inference. See https://numpy.org/doc/stable/reference/typing.html#d-arrays
    # for more information on why this should be done.
    plaquette_array_list: list[list[int]] = to2dlist(plaquette_array)
    for row_index, line in enumerate(plaquette_array_list):
        for column_index, plaquette_index in enumerate(line):
            if plaquette_index != 0:
                # Computing the offset that should be applied to each qubits.
                plaquette = plaquettes[plaquette_index]
                qubit_offset = Shift2D(
                    plaquette.origin.x + column_index * increments.x,
                    plaquette.origin.y + row_index * increments.y,
                )
                # Warning: the variable `mapped_scheduled_circuit` shares with
                #          `plaquette_circuits[plaquette_index]` a reference to
                #          the circuit data-structure. This is not an issue here
                #          as we never attempt to mutate that circuit before
                #          calling `relabel_circuits_qubit_indices`, that
                #          explicitly returns a copy of its inputs, and do not
                #          mutate them either.
                scheduled_circuit = plaquette_circuits[plaquette_index]
                mapped_scheduled_circuit = scheduled_circuit.map_to_qubits(
                    lambda q: q + qubit_offset, inplace_qubit_map=False
                )
                all_scheduled_circuits.append(mapped_scheduled_circuit)
                additional_mergeable_instructions |= plaquette.mergeable_instructions

    # Merge everything, but first make sure that the circuits are compatible.
    # Note that relabel_circuits_qubit_indices guarantees in its documentation
    # that the input circuits are not mutated but rather copied. This allows us
    # to not deepcopy the circuits earlier in the function.
    all_scheduled_circuits, qubit_map = relabel_circuits_qubit_indices(all_scheduled_circuits)
    return merge_scheduled_circuits(
        all_scheduled_circuits, qubit_map, additional_mergeable_instructions
    )
