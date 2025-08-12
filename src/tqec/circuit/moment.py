"""Defines a class analogous to ``cirq.Moment``.

This module defines :class:`Moment` that is very close to the external
`cirq.Moment <https://quantumai.google/reference/python/cirq/Moment>`_
class.

Internally, :class:`Moment` stores the instructions using ``stim.Circuit``
instead of using ``cirq`` data-structures.

"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence
from copy import deepcopy
from typing import Any, cast

import stim

from tqec.circuit.qubit import count_qubit_accesses, get_used_qubit_indices
from tqec.utils.exceptions import TQECError
from tqec.utils.instructions import is_annotation_instruction


class MultipleOperationsOnSameQubitError(TQECError):
    def __init__(self, qubits: Sequence[int]):
        """Create a new instance of the exception.

        Args:
            qubits: qubit indices that are targeted by several instructions at the same timestep.

        """
        self._qubits = sorted(qubits)
        super().__init__(
            "Moment instances cannot be initialized with a stim.Circuit "
            "instance containing gates applied on the same qubit. Found "
            "multiple gates applied on the following qubits: "
            f"{self._qubits}."
        )

    @property
    def qubits(self) -> list[int]:
        """Return the qubits that are targeted by several instructions at the same timestep."""
        return self._qubits  # pragma: no cover


class Moment:
    """A collection of instructions that can be executed in parallel.

    This class is a collection of ``stim.CircuitInstruction`` instances that
    can all be executed in parallel. That means that it maintains the following
    invariant:

    For each instruction contained in any instance of this class, exactly
    one of the following assertions is true:

    1. The instruction is an annotation (e.g., ``QUBIT_COORDS``, ``DETECTOR``, ...),
    2. It is the only instruction of the :class:`Moment` instance to be applied
        on its targets. In other words, no other instructions in the :class:`Moment`
        instance can be applied on the targets this instruction is applied to.

    In practice, that means that this class match closely the definition of
    `cirq.Moment <https://quantumai.google/reference/python/cirq/Moment>`_.
    The only minor different is that ``cirq`` only uses the second assertion
    above (meaning that an annotation might push a quantum gate to the next
    moment, even though the annotation is never executed in hardware).

    """

    def __init__(
        self,
        circuit: stim.Circuit,
        used_qubits: set[int] | None = None,
        _avoid_checks: bool = False,
    ) -> None:
        """Initialize a :class:`Moment` instance.

        Args:
            circuit: collection of instructions representing the :class:`Moment`.
                It should represent a valid moment, see the class documentation
                for a detailed explanation of the pre-conditions.
            used_qubits: a set of qubit indices used in the provided ``circuit``.
                It is the user responsibility to ensure that this input is
                correct if it is provided, as any non-``None`` input will not be
                checked. Defaults to ``None``, which triggers a call to
                :func:`.get_used_qubit_indices` to initialise the indices.
            _avoid_checks: avoid checking the validity of the provided ``circuit``.
                This parameter can be used when the user knows that the provided
                ``circuit`` is a valid moment (and so checks the pre-conditions
                listed in the class documentation). Defaults to ``False``, which
                triggers a systematic check and might raise if the provided
                ``circuit`` is not a valid moment.

        Raises:
            TQECError: if the provided ``circuit`` contains one or more
                ``TICK`` instruction.
            TQECError: if the provided ``circuit`` contains at least 2
                non-annotation instructions that are applied on the same qubit
                target.
            TQECError: if the provided ``circuit`` contains a ``REPEAT``
                block instruction.

        """
        if not _avoid_checks:
            Moment.check_is_valid_moment(circuit)
        self._circuit: stim.Circuit = circuit
        self._used_qubits: set[int]
        if used_qubits is not None:
            self._used_qubits = used_qubits
        else:
            self._used_qubits = get_used_qubit_indices(self._circuit)

    @property
    def circuit(self) -> stim.Circuit:
        """Get the underlying circuit containing the operations."""
        return self._circuit

    @staticmethod
    def check_is_valid_moment(circuit: stim.Circuit) -> None:
        """Check if the provided circuit can be considered a valid moment.

        Args:
            circuit: instance to check.

        Raises:
            TQECError: if the provided ``circuit`` contains one or more
                ``TICK`` instruction.
            TQECError: if the provided ``circuit`` contains at least 2
                non-annotation instructions that are applied on the same qubit
                target.
            TQECError: if the provided ``circuit`` contains a ``REPEAT``
                block instruction.

        """
        if circuit.num_ticks > 0:
            raise TQECError(
                "Cannot initialize a Moment with a stim.Circuit instance "
                "containing at least one TICK instruction."
            )
        qubit_usage = count_qubit_accesses(circuit)
        multi_used_qubits = [qi for qi, usage_count in qubit_usage.items() if usage_count > 1]
        if multi_used_qubits:
            raise MultipleOperationsOnSameQubitError(multi_used_qubits)
        if any(isinstance(inst, stim.CircuitRepeatBlock) for inst in circuit):
            raise TQECError(
                "Moment instances should no contain any instance of stim.CircuitRepeatBlock."
            )

    @staticmethod
    def from_instructions(instructions: Iterable[stim.CircuitInstruction]) -> Moment:
        """Construct a :class:`Moment` instance from the provided ``instructions``."""
        circuit = stim.Circuit()
        for inst in instructions:
            circuit.append(inst)
        return Moment(circuit)

    @property
    def qubits_indices(self) -> set[int]:
        """Return the qubit indices this moment operates on.

        Note:
            Some instructions are considered annotations (e.g., ``QUBIT_COORDS``,
            see :data:`~tqec.circuit.qubit.NON_COMPUTATION_INSTRUCTIONS` for an
            exhaustive list). These instructions are ignored by this property,
            meaning that the qubits they operate on will only be returned by
            this property iff another non-annotation instruction is applied on
            said qubits.

        """
        return self._used_qubits

    def contains_instruction(self, instruction_name: str) -> bool:
        """Return ``True`` if ``self`` contains at least one operation with the provided name."""
        return any(instr.name == instruction_name for instr in self._circuit)

    def remove_all_instructions_inplace(self, instructions_to_remove: frozenset[str]) -> None:
        """Remove in-place all the instructions with a name in ``instructions_to_remove``."""
        new_circuit = stim.Circuit()
        for inst in self._circuit:
            if inst.name in instructions_to_remove:
                continue
            new_circuit.append(inst)
        self._circuit = new_circuit

    def __iadd__(self, other: Moment) -> Moment:
        """Add instructions in-place in ``self``."""
        both_sides_used_qubits = self._used_qubits.intersection(other._used_qubits)
        if both_sides_used_qubits:
            raise TQECError("Trying to add an overlapping quantum circuit to a Moment instance.")
        self._circuit += other._circuit
        return self

    def __add__(self, other: Moment) -> Moment:
        """Add instructions of ``self`` and ``other`` in a new instance."""
        both_sides_used_qubits = self._used_qubits.intersection(other._used_qubits)
        if both_sides_used_qubits:
            raise TQECError("Trying to add an overlapping quantum circuit to a Moment instance.")
        cpy = deepcopy(self)
        cpy += other
        return cpy

    @staticmethod
    def _get_used_qubit_indices(
        targets: Iterable[int | stim.GateTarget],
    ) -> list[int]:
        qubits: list[int] = []
        for target in targets:
            if isinstance(target, int):
                qubits.append(target)
                continue
            # isinstance(target, stim.GateTarget)
            if target.is_qubit_target:
                assert isinstance(target.qubit_value, int)  # type checker is happy
                qubits.append(target.qubit_value)
        return qubits

    def append(
        self,
        name_or_instr: str | stim.CircuitInstruction,
        targets: Iterable[int | stim.GateTarget] | None = None,
        args: Iterable[float] | None = None,
    ) -> None:
        """Append an instruction to the :class:`Moment`.

        Note:
            if you append an annotation (e.g., ``DETECTOR`` or ``QUBIT_COORDS``)
            then you should use :meth:`append_annotation` that is more efficient.

        Args:
            name_or_instr: either the name of the instruction to append or the
                actual instruction. If the name is provided, ``targets`` and
                ``args`` are used to build the ``stim.CircuitInstruction``
                instance that will be appended. Else, they are not accessed.
            targets: if ``name_or_instr`` is a string representing the instruction
                name, this argument represent the targets the instruction should
                be applied on. Else, it is not used.
            args: if ``name_or_instr`` is a string representing the instruction
                name, this argument represent the arguments the instruction
                should be applied with. Else, it is not used.

        """
        if targets is None:
            targets = tuple()
        if args is None:
            args = tuple()

        instruction: stim.CircuitInstruction
        if isinstance(name_or_instr, str):
            instruction = stim.CircuitInstruction(name_or_instr, targets, args)
        else:
            instruction = name_or_instr

        if is_annotation_instruction(instruction):
            self.append_annotation(instruction)
            return

        # Checking Moment invariant
        instruction_qubits = Moment._get_used_qubit_indices(
            targets if isinstance(name_or_instr, str) else name_or_instr.targets_copy()
        )
        overlapping_qubits = self._used_qubits.intersection(instruction_qubits)
        if overlapping_qubits:
            raise TQECError(
                f"Cannot add {instruction} to the Moment due to qubit(s) "
                f"{overlapping_qubits} being already in use."
            )
        self._used_qubits.update(instruction_qubits)
        self._circuit.append(instruction)

    def append_annotation(self, annotation_instruction: stim.CircuitInstruction) -> None:
        """Append an annotation instruction to ``self``.

        This method is way more efficient than :meth:`append` to append an
        annotation. This is thanks to the fact that annotations are not using
        any qubit and so can be appended without checking that the instruction
        does not apply on already used qubits.

        Args:
            annotation_instruction: an annotation to append to the moment
                represented by ``self``.

        Raises:
            TQECError: if ``not is_annotation_instruction(annotation_instruction)``.

        """
        if not is_annotation_instruction(annotation_instruction):
            raise TQECError(
                "The method append_annotation only supports appending "
                f"annotations. Found instruction {annotation_instruction.name} "
                "That is not a valid annotation. Call append_instruction for "
                "generic instructions."
            )
        self._circuit.append(annotation_instruction)

    @property
    def instructions(self) -> Iterator[stim.CircuitInstruction]:
        """Iterator over all the instructions contained in ``self``."""
        # We can ignore the type error below because:
        # 1. if a Moment instance is created with a stim.CircuitRepeatBlock
        #    instance, it will raise an exception.
        # 2. `Moment.append` is the only method that may add an instance of
        #    stim.CircuitRepeatBlock, but its typing information explicitly
        #    prevents that case.
        # So we know for sure that there are only `stim.CircuitInstruction`
        # instances.
        yield from self._circuit  # type: ignore

    @property
    def num_measurements(self) -> int:
        """Return the number of measurements in the :class:`Moment` instance."""
        # Mypy is showing an error here:
        # error: Returning Any from function declared to return "int"
        # I do not understand why, but it probably has to do with Stim typing
        # so let's ignore it for the moment.
        return self._circuit.num_measurements  # type: ignore

    def filter_by_qubits(self, qubits_to_keep: Iterable[int]) -> Moment:
        """Return a new instance containing only the instructions applied on the provided qubits.

        Any operation from ``self`` that is applied to at least one qubit that is not in the
        provided ``qubits_to_keep`` will not be present in the returned :class:`Moment` instance.
        """
        qubits = frozenset(qubits_to_keep)
        used_qubits: set[int] = set()
        new_circuit = stim.Circuit()
        for instruction in self.instructions:
            targets: list[stim.GateTarget] = []
            for target_group in instruction.target_groups():
                qubit_targets = [
                    cast(int, t.qubit_value) for t in target_group if t.is_qubit_target
                ]
                if any(q not in qubits for q in qubit_targets):
                    continue
                targets.extend(target_group)
                used_qubits.update(qubit_targets)
            if targets:
                new_circuit.append(instruction.name, targets, instruction.gate_args_copy())
        return Moment(new_circuit, used_qubits=used_qubits, _avoid_checks=True)

    @property
    def is_empty(self) -> bool:
        """Return ``True`` if the :class:`Moment` instance is empty."""
        return len(self._circuit) == 0

    def __copy__(self) -> Moment:
        return Moment(  # pragma: no cover
            self._circuit,
            used_qubits=self._used_qubits,
            _avoid_checks=True,
        )

    def __deepcopy__(self, _: dict[Any, Any]) -> Moment:
        return Moment(
            self._circuit.copy(),
            used_qubits=self._used_qubits,
            _avoid_checks=True,
        )

    def with_mapped_qubit_indices(self, qubit_index_map: dict[int, int]) -> Moment:
        """Map the qubit **indices** on whom the :class:`Moment` instance is applied.

        Note:
            This method has to iterate over all the instructions in ``self`` and
            change the gate target they are applied on.

        Args:
            qubit_index_map: the map used to modify the qubit targets.

        Returns:
            a modified copy of ``self`` with the qubit gate targets mapped according
            to the provided ``qubit_index_map``.

        """
        circuit = stim.Circuit()
        for instr in self.instructions:
            mapped_targets: list[stim.GateTarget] = []
            for target in instr.targets_copy():
                # Non qubit targets are left untouched.
                if not target.is_qubit_target:
                    mapped_targets.append(target)
                    continue
                # Qubit targets are mapped using `qubit_index_map`
                target_qubit = cast(int, target.qubit_value)
                mapped_targets.append(
                    stim.GateTarget(qubit_index_map[target_qubit])
                    if not target.is_inverted_result_target
                    else stim.GateTarget(-qubit_index_map[target_qubit])
                )
            circuit.append(instr.name, mapped_targets, instr.gate_args_copy())
        return Moment(
            circuit,
            used_qubits={qubit_index_map[q] for q in self._used_qubits},
            _avoid_checks=True,
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Moment) and self._circuit == other._circuit

    def __hash__(self) -> int:
        raise NotImplementedError(f"Cannot hash efficiently a {type(self).__name__}.")

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the :class:`Moment` instance.

        The dictionary is intended to be used as a JSON object.

        """
        return {
            "circuit": str(self._circuit),
            "used_qubits": list(self._used_qubits),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Moment:
        """Return a :class:`Moment` instance from its dictionary representation.

        Args:
            data: dictionary with the keys ``circuit`` and ``used_qubits``.

        Returns:
            a new instance of :class:`Moment` with the provided ``circuit`` and
            ``used_qubits``.

        """
        circuit = stim.Circuit(data["circuit"])
        used_qubits = set(data["used_qubits"])
        return Moment(circuit, used_qubits=used_qubits, _avoid_checks=True)


def iter_stim_circuit_without_repeat_by_moments(
    circuit: stim.Circuit, collected_before_use: bool = True
) -> Iterator[Moment]:
    """Iterate over the ``stim.Circuit`` by moments.

    A moment in a ``stim.Circuit`` is a sequence of instructions between two ``TICK``
    instructions. Note that ``stim.CircuitRepeatBlock`` instances are explicitly not
    supported and no such instance should appear in the provided circuit.

    Args:
        circuit: circuit to iterate over. Should not contain any ``REPEAT`` block.
        collected_before_use: if ``True``, the returned :class:`Moment` instances
            will contain a copy of the temporary ``stim.Circuit`` instance
            representing the moment. This is needed if the yielded
            :class:`Moment` instances are not used directly because the
            underlying ``stim.Circuit`` instance is cleared when resuming the
            generator.

    Yields:
        :class`Moment` instances.

    Raises:
        TQECError: if the provided ``circuit`` contains at least one
            ``stim.CircuitRepeatBlock`` instance.
        TQECError: if the provided ``circuit`` ``TICK`` instructions are not
            inserted such that instructions between two ``TICK`` instructions
            are always applied on disjoint sets of qubits.

    """
    copy_func: Callable[[stim.Circuit], stim.Circuit] = (
        (lambda c: c.copy()) if collected_before_use else (lambda c: c)
    )
    cur_moment = stim.Circuit()
    for inst in circuit:
        if isinstance(inst, stim.CircuitRepeatBlock):
            raise TQECError(
                "Found an instance of stim.CircuitRepeatBlock which is "
                "explicitly not supported by this method."
            )
        elif inst.name == "TICK":
            yield Moment(copy_func(cur_moment))
            cur_moment.clear()
        else:
            cur_moment.append(inst)
    # No need to copy the last moment
    yield Moment(cur_moment)
