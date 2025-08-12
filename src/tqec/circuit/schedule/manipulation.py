"""Defines functions to modify or merge :class:`.ScheduledCircuit` instances.

This module implement a few central functions for the :mod:`tqec` library:

- :func:`remove_duplicate_instructions` to remove some instructions appearing
  twice in a single moment (most of the time due to data qubit
  reset/measurements that are defined by each plaquette, even on qubits shared
  with other plaquettes, leading to duplicates).
- :func:`merge_scheduled_circuits` that merge several
  :class:`~tqec.circuit.schedule.circuit.ScheduledCircuit` instances into one.
- :func:`relabel_circuits_qubit_indices` to prepare several
  :class:`~tqec.circuit.schedule.circuit.ScheduledCircuit` before merging them.
  This function is called internally by :func:`merge_scheduled_circuits` but
  might be useful at other places and so is kept public.

"""

from __future__ import annotations

import functools
import itertools
import operator
import warnings
from collections.abc import Iterable, Sequence

import stim

from tqec.circuit.moment import Moment
from tqec.circuit.qubit import GridQubit
from tqec.circuit.qubit_map import QubitMap
from tqec.circuit.schedule.circuit import ScheduledCircuit
from tqec.circuit.schedule.schedule import Schedule
from tqec.utils.exceptions import TQECError, TQECWarning


class _ScheduledCircuits:
    def __init__(self, circuits: list[ScheduledCircuit], global_qubit_map: QubitMap) -> None:
        """Represent a collection of :class:`.ScheduledCircuit` instances.

        This class aims at providing accessors for several compatible instances
        of :class:`~tqec.circuit.schedule.circuit.ScheduledCircuit`. It allows
        to iterate on gates globally, for all the managed instances of
        :class:`~tqec.circuit.schedule.circuit.ScheduledCircuit`, and implement
        a few other accessor methods to help with the task of merging multiple
        :class:`~tqec.circuit.schedule.circuit.ScheduledCircuit` together.

        Args:
            circuits: the instances that should be managed. Note that the
                instances provided here have to be "compatible" with each
                other.
            global_qubit_map: a unique qubit map that can be used to map qubits
                to indices for all the provided ``circuits``.

        """
        # We might need to remap qubits to avoid index collision on several
        # circuits.
        self._circuits = circuits
        self._global_qubit_map = global_qubit_map
        self._iterators = [circuit.scheduled_moments for circuit in self._circuits]
        self._current_moments = [next(it, None) for it in self._iterators]

    def has_pending_moment(self) -> bool:
        """Check if any of the managed instances has a pending moment.

        Any moment that has not been collected by using collect_moment is considered to be pending.

        Any moment that has not been collected by using ``collect_moment`` is considered to be
        pending.

        """
        return any(self._has_pending_moment(i) for i in range(len(self._circuits)))

    def _has_pending_moment(self, index: int) -> bool:
        """Check if the managed instance at the given index has a pending operation."""
        return self._current_moments[index] is not None

    def _peek_scheduled_moment(self, index: int) -> tuple[int, Moment]:
        """Recover **without collecting** pending operations for the instance at the given index."""
        ret = self._current_moments[index]
        assert ret is not None
        return ret

    def _pop_scheduled_moment(self, index: int) -> tuple[int, Moment]:
        """Recover and mark as collected the pending moment for the instance at the given index.

        Raises:
            AssertionError: ``if not self.has_pending_operation(index)``.

        """
        ret = self._current_moments[index]
        if ret is None:
            raise TQECError(
                "Trying to pop a Moment instance from a ScheduledCircuit with "
                "all its moments already collected."
            )
        self._current_moments[index] = next(self._iterators[index], None)
        return ret

    @property
    def number_of_circuits(self) -> int:
        return len(self._circuits)

    def collect_moments_at_minimum_schedule(self) -> tuple[int, list[Moment]]:
        """Collect all the moments that can be collected.

        This method collects and returns a list of all the moments that should
        be scheduled next.

        Returns:
            a list of :class:`~tqec.circuit.moment.Moment` instances that should
            be added next to the QEC circuit.

        """
        assert self.has_pending_moment()
        circuit_indices_organised_by_schedule: dict[int, list[int]] = dict()
        for circuit_index in range(self.number_of_circuits):
            if not self._has_pending_moment(circuit_index):
                continue
            schedule, _ = self._peek_scheduled_moment(circuit_index)
            circuit_indices_organised_by_schedule.setdefault(schedule, list()).append(circuit_index)

        minimum_schedule = min(circuit_indices_organised_by_schedule.keys())
        moments_to_return: list[Moment] = list()
        for circuit_index in circuit_indices_organised_by_schedule[minimum_schedule]:
            _, moment = self._pop_scheduled_moment(circuit_index)
            moments_to_return.append(moment)
        return minimum_schedule, moments_to_return

    @property
    def q2i(self) -> dict[GridQubit, int]:
        return self._global_qubit_map.q2i


def _sort_target_groups(
    targets: Iterable[list[stim.GateTarget]],
) -> list[list[stim.GateTarget]]:
    def _sort_key(target_group: Iterable[stim.GateTarget]) -> tuple[int, ...]:
        return tuple(t.value for t in target_group)

    return sorted(targets, key=_sort_key)


def remove_duplicate_instructions(
    instructions: list[stim.CircuitInstruction],
    mergeable_instruction_names: frozenset[str],
) -> list[stim.CircuitInstruction]:
    """Remove all the duplicate instructions from the given list.

    Note:
        This function guarantees the following post-conditions on the returned
        results:

        - Instructions with a name that is not in ``mergeable_instruction_names``
          are returned at the front of the returned list, in the same relative
          ordering as provided in ``instructions`` input.
        - Instructions with a name that is in ``mergeable_instruction_names``
          will be returned after all the instructions with a name that does not
          appear in ``mergeable_instruction_names``. The order in which these
          instructions are returned is not guaranteed and can change between
          executions.

    Warning:
        this function **does not keep instruction ordering**. It is intended to
        be used with input ``instructions`` that, once de-duplication has been
        applied, form a valid moment, which means that each instruction can be
        executed in parallel, and so their order in the returned list does not
        matter.

        If that is not your case, take extra care to the output of this
        function as it will likely introduce hard-to-debug issues. To prevent
        such potential misuse, this function checks for such cases and outputs
        a warning if it happens.

    Returns:
        a list containing a copy of the ``stim.CircuitInstruction`` instances
        from the given instructions but without any duplicate.

    """
    # Separate mergeable operations from non-mergeable ones.
    mergeable_operations: dict[tuple[str, tuple[float, ...]], set[tuple[stim.GateTarget, ...]]] = {}
    final_operations: list[stim.CircuitInstruction] = list()
    for inst in instructions:
        if inst.name in mergeable_instruction_names:
            # Mergeable operations are automatically merged thanks to
            # the use of a set here.
            mergeable_operations.setdefault(
                (inst.name, tuple(inst.gate_args_copy())), set()
            ).update(tuple(group) for group in inst.target_groups())
        else:
            final_operations.append(inst)
    # Add the merged operations into the final ones
    final_operations.extend(
        stim.CircuitInstruction(
            name,
            functools.reduce(operator.iadd, _sort_target_groups([list(t) for t in targets]), []),
            args,
        )
        for (name, args), targets in mergeable_operations.items()
    )
    # Warn if the output instructions do not form a valid moment, as this is
    # likely a misuse of this function.
    circuit = stim.Circuit()
    for instr in final_operations:
        circuit.append(instr)
    try:
        Moment.check_is_valid_moment(circuit)
    except TQECError as e:
        warnings.warn(
            "The instructions obtained at the end of the "
            "`remove_duplicate_instructions` function do not form a valid "
            "moment. You are likely misusing the function. Final instructions "
            "obtained and gathered into a single stim.Circuit: "
            f"\n{circuit}\nReason:\n{e}",
            TQECWarning,
        )
    return final_operations


def merge_instructions(
    instructions: list[stim.CircuitInstruction],
) -> list[stim.CircuitInstruction]:
    """Merge instructions with the same name and arguments.

    Returns:
        a list containing a copy of the ``stim.CircuitInstruction`` instances
        from the given instructions but merged.

    """
    instructions_merger: dict[tuple[str, tuple[float, ...]], list[list[stim.GateTarget]]] = {}
    for instruction in instructions:
        args = tuple(instruction.gate_args_copy())
        instructions_merger.setdefault((instruction.name, args), []).extend(
            instruction.target_groups()
        )
    return [
        stim.CircuitInstruction(name, functools.reduce(operator.iadd, targets, []), args)
        for (name, args), targets in instructions_merger.items()
    ]


def merge_scheduled_circuits(
    circuits: list[ScheduledCircuit],
    global_qubit_map: QubitMap,
    mergeable_instructions: Iterable[str] = (),
) -> ScheduledCircuit:
    """Merge several :class:`.ScheduledCircuit` instances into one instance.

    This function takes several **compatible** scheduled circuits as input and
    merge them, respecting their schedules, into a unique
    :class:`~tqec.circuit.schedule.circuit.ScheduledCircuit` instance that will
    then be returned to the caller.

    The provided circuits should be compatible between each other. Compatible
    circuits are circuits that can all be described with a unique global qubit
    map. In other words, if two circuits from the list of compatible circuits
    use the same qubit index, that should mean that they use the same qubit.
    You can obtain compatible circuits by using
    :func:`relabel_circuits_qubit_indices`.

    Args:
        circuits: **compatible** circuits to merge.
        global_qubit_map: global qubit map for all the provided ``circuits``.
        mergeable_instructions: a list of instruction names that are considered
            mergeable. Duplicate instructions with a name in this list will be
            merged into a single instruction.

    Returns:
        a circuit representing the merged scheduled circuits given as input.

    """
    scheduled_circuits = _ScheduledCircuits(circuits, global_qubit_map)

    all_moments: list[Moment] = []
    all_schedules = Schedule()
    global_i2q = QubitMap({i: q for q, i in scheduled_circuits.q2i.items()})

    while scheduled_circuits.has_pending_moment():
        schedule, moments = scheduled_circuits.collect_moments_at_minimum_schedule()
        # Flatten the moments into a list of operations to perform some modifications
        instructions: list[stim.CircuitInstruction] = functools.reduce(
            operator.iadd, (list(moment.instructions) for moment in moments), []
        )
        # Avoid duplicated operations. Any operation that have the Plaquette.get_mergeable_tag() tag
        # is considered mergeable, and can be removed if another operation in the list
        # is considered equal (and has the mergeable tag).
        deduplicated_instructions = remove_duplicate_instructions(
            instructions,
            mergeable_instruction_names=frozenset(mergeable_instructions),
        )
        merged_instructions = merge_instructions(deduplicated_instructions)
        circuit = stim.Circuit()
        for inst in merged_instructions:
            circuit.append(
                inst.name,
                functools.reduce(operator.iadd, _sort_target_groups(inst.target_groups()), []),
                inst.gate_args_copy(),
            )
        all_moments.append(Moment(circuit))
        all_schedules.append(schedule)

    return ScheduledCircuit(all_moments, all_schedules, global_i2q, _avoid_checks=True)


def relabel_circuits_qubit_indices(
    circuits: Sequence[ScheduledCircuit],
) -> tuple[list[ScheduledCircuit], QubitMap]:
    """Relabel the qubit indices of the provided circuits to avoid collision.

    When several :class:`~tqec.circuit.schedule.circuit.ScheduledCircuit` are
    constructed without a global knowledge of all the qubits, qubit indices used
    by each instance likely overlap. This is an issue when we try to merge such
    circuits because one index might represent a different qubit depending on
    the circuit it is used in.

    This function takes a sequence of circuits and relabel their qubits to avoid
    such collisions.

    Warning:
        all the qubit targets used in each of the provided circuits should have
        a corresponding entry in the circuit qubit map for this function to work
        correctly. If that is not the case, a ``KeyError`` will be raised.

    Raises:
        KeyError: if any of the provided circuit contains a qubit target that is
            not present in its qubit map.

    Args:
        circuits: circuit instances to remap. This parameter is not mutated by
            this function and is only used in read-only mode.

    Returns:
        the same circuits with updated qubit indices as well as the global qubit
        indices map that has been used. Qubits in the returned global qubit map
        are assigned to an index such that:

        1. the sequence of indices is ``range(0, len(qubit_map))``.
        2. qubits are assigned indices in sorted order.

    """
    # First, get a global qubit index map.
    # Using itertools to avoid the edge case `len(circuits) == 0`
    needed_qubits = frozenset(itertools.chain.from_iterable([c.qubits for c in circuits]))
    global_qubit_map = QubitMap.from_qubits(sorted(needed_qubits))
    global_q2i = global_qubit_map.q2i
    # Then, get the remapped circuits. Note that map_qubit_indices should
    # have approximately the same runtime cost whatever the value of inplace
    # so we ask for a new instance to avoid keeping a reference to the given
    # circuits.
    relabeled_circuits: list[ScheduledCircuit] = []
    for circuit in circuits:
        local_indices_to_global_indices = {
            local_index: global_q2i[q] for local_index, q in circuit.qubit_map.items()
        }
        relabeled_circuits.append(
            circuit.map_qubit_indices(local_indices_to_global_indices, inplace=False)
        )
    return relabeled_circuits, global_qubit_map
