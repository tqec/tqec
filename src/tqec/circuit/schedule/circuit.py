"""Defines :class:`.ScheduledCircuit` that represents a quantum circuit with a specific schedule.

This module defines the class used to represent a quantum circuit. It is a
"scheduled" circuit. Such circuits are composed of a finite number of ordered
:class:`~tqec.circuit.moment.Moment` instances that are each associated to an
integer in a strictly increasing list of integers (called "schedule" and
represented by instances of :class:`~.schedule.schedule.Schedule`).

"""

from __future__ import annotations

import bisect
from collections.abc import Callable, Iterable, Iterator, Sequence
from copy import copy, deepcopy
from typing import Any

import stim

from tqec.circuit.moment import Moment, iter_stim_circuit_without_repeat_by_moments
from tqec.circuit.qubit import GridQubit
from tqec.circuit.qubit_map import QubitMap, get_qubit_map
from tqec.circuit.schedule.exception import ScheduleError
from tqec.circuit.schedule.schedule import Schedule
from tqec.utils.exceptions import TQECError
from tqec.utils.instructions import is_annotation_instruction


class ScheduledCircuit:
    def __init__(
        self,
        moments: list[Moment],
        schedule: Schedule | list[int] | int,
        qubit_map: QubitMap,
        _avoid_checks: bool = False,
    ) -> None:
        """Represent a quantum circuit with scheduled moments.

        This class aims at representing a ``stim.Circuit`` instance that has all
        its moments scheduled, i.e., associated with a time slice.

        This class explicitly does not support ``stim.CircuitRepeatBlock`` (i.e.,
        ``REPEAT`` instruction). It will raise an exception if such an
        instruction is found.

        Args:
            moments: moments representing the computation that is scheduled.
                The provided ``moments`` should not contain any ``QUBIT_COORDS``
                instructions. Instead, the qubit coordinates should be provided
                through the ``qubit_map`` parameter.
            schedule: schedule of the provided ``moments``. If an integer is
                provided, each moment of the provided ``stim.Circuit`` is
                scheduled sequentially, starting by the provided integer.
            qubit_map: a map from indices to qubits that is used to re-create
                ``QUBIT_COORDS`` instructions when generating a ``stim.Circuit``.
            _avoid_checks: if True, the inputs are not checked for pre-condition
                violation and it is up to the user to ensure that
                :class:`ScheduledCircuit` pre-conditions are checked by the
                provided input.

        Raises:
            ScheduleError: if the provided ``schedule`` is invalid.
            TQECError: if the provided ``circuit`` contains at least one
                ``stim.CircuitRepeatBlock`` instance.
            TQECError: if the provided ``circuit`` contains at least one
                ``QUBIT_COORDS`` instruction after the first ``TICK`` instruction.

        """
        # Handle each input type explicitly due to type checker
        if isinstance(schedule, int):
            schedule_temp = list(range(schedule, schedule + len(moments)))
            schedule = Schedule(schedule=schedule_temp)
        elif isinstance(schedule, list) and not isinstance(schedule, Schedule):
            schedule = Schedule(schedule=schedule)

        if len(moments) != len(schedule):
            raise ScheduleError(
                "ScheduledCircuit expects all the provided moments to be scheduled. "
                f"Got {len(moments)} moments but {len(schedule)} schedules."
            )
        if not _avoid_checks and any(m.contains_instruction("QUBIT_COORDS") for m in moments):
            raise ScheduleError(
                "ScheduledCircuit instance expects the input `stim.Circuit` to "
                "not contain any QUBIT_COORDS instruction. Found at least one "
                "moment with a QUBIT_COORDS instruction."
            )

        non_empty_moments_indices = [i for i, m in enumerate(moments) if not m.is_empty]
        self._moments: list[Moment] = [moments[i] for i in non_empty_moments_indices]
        self._qubit_map: QubitMap = qubit_map
        self._schedule = Schedule([schedule[i] for i in non_empty_moments_indices])

    @staticmethod
    def empty() -> ScheduledCircuit:
        """Return an empty :class:`ScheduledCircuit` instance."""
        return ScheduledCircuit([], Schedule(), QubitMap(), _avoid_checks=True)

    @staticmethod
    def from_circuit(
        circuit: stim.Circuit,
        schedule: Schedule | list[int] | int = 0,
        qubit_map: QubitMap | None = None,
    ) -> ScheduledCircuit:
        """Build a :class:`ScheduledCircuit` instance from a circuit and a schedule.

        Args:
            circuit: the instance of ``stim.Circuit`` that is scheduled. Should
                not contain any instance of ``stim.CircuitRepeatBlock``.
            schedule: a sorted list of positive integers or a positive integer.
                If a list is given, it should contain as many values as there
                are moments in the provided ``stim.Circuit`` instance. If an
                integer is provided, each moment of the provided ``stim.Circuit``
                is scheduled sequentially, starting by the provided schedule.
            qubit_map: a map from indices to qubits. If None, this function will
                try to extract the qubit coordinates from the ``QUBIT_COORDS``
                instructions found in the provided ``circuit``. Else, the
                provided map will be used.

        Raises:
            ScheduleError: if the provided ``schedule`` is invalid.
            TQECError: if the provided ``circuit`` contains at least one
                ``stim.CircuitRepeatBlock`` instance.
            TQECError: if the provided ``circuit`` contains at least one
                ``QUBIT_COORDS`` instruction after the first ``TICK`` instruction.

        """
        # Handle each input type explicitly due to type checker
        if isinstance(schedule, int):
            schedule_temp = list(range(schedule, schedule + circuit.num_ticks + 1))
            schedule = Schedule(schedule=schedule_temp)
        elif isinstance(schedule, list) and not isinstance(schedule, Schedule):
            schedule = Schedule(schedule=schedule)

        # Ensure that the provided circuit does not contain any
        # `stim.CircuitRepeatBlock` instance.
        if any(isinstance(inst, stim.CircuitRepeatBlock) for inst in circuit):
            raise ScheduleError(
                "stim.CircuitRepeatBlock instances are not supported in a "
                "ScheduledCircuit instance."
            )
        moments: list[Moment] = list(
            iter_stim_circuit_without_repeat_by_moments(circuit, collected_before_use=True)
        )
        if not moments:
            return ScheduledCircuit.empty()

        if any(m.contains_instruction("QUBIT_COORDS") for m in moments[1:]):
            raise ScheduleError(
                "ScheduledCircuit instance expects the input `stim.Circuit` to "
                "only contain QUBIT_COORDS instructions before the first TICK."
            )
        if qubit_map is None:
            # Here, we know for sure that no qubit is (re)defined in another place
            # than the first moment, so we can directly get qubit coordinates from
            # that moment.
            qubit_map = get_qubit_map(moments[0].circuit)
        # And because we want the cleanest possible moments, we can remove the
        # `QUBIT_COORDS` instructions from the first moment.
        moments[0].remove_all_instructions_inplace(frozenset(["QUBIT_COORDS"]))
        return ScheduledCircuit(moments, schedule, qubit_map, _avoid_checks=True)

    @property
    def schedule(self) -> Schedule:
        """Schedule of the internal moments."""
        return self._schedule

    def get_qubit_coords_definition_preamble(self, shift_to_positive: bool = False) -> stim.Circuit:
        """Get a circuit with only ``QUBIT_COORDS`` instructions.

        Args:
            shift_to_positive: if ``True``, the qubit coordinates are shift such
                that they are all positive. Their relative positioning stays
                unchanged.

        """
        return self._qubit_map.to_circuit(shift_to_positive)

    def get_circuit(
        self, include_qubit_coords: bool = True, shift_to_positive: bool = False
    ) -> stim.Circuit:
        """Build and return the ``stim.Circuit`` instance represented by ``self``.

        Args:
            include_qubit_coords: if ``True``, ``QUBIT_COORDS`` annotations are
                added at the beginning of the returned circuit to declare the
                coordinates of used qubits. Else, no ``QUBIT_COORDS`` annotation
                is added.
            shift_to_positive: if ``True``, the qubit coordinates are shift such
                that they are all positive. Their relative positioning stays
                unchanged.

        Warning:
            The circuit is re-built at each call! Use that function wisely.

        Returns:
            ``stim.Circuit`` instance represented by ``self``.

        """
        ret = stim.Circuit()
        if not self._moments:
            return ret

        # Appending the QUBIT_COORDS instructions first.
        if include_qubit_coords:
            ret += self.get_qubit_coords_definition_preamble(shift_to_positive)

        # Building the actual circuit.
        current_schedule: int = 0
        last_schedule: int = self._schedule[-1]
        for sched, moment in zip(self._schedule, self._moments):
            for _ in range(current_schedule, sched):
                ret.append("TICK", [], [])
                current_schedule += 1
            ret += moment.circuit
            if current_schedule != last_schedule:
                ret.append("TICK", [], [])
                current_schedule += 1

        return ret

    def map_qubit_indices(
        self, qubit_index_map: dict[int, int], inplace: bool = False
    ) -> ScheduledCircuit:
        """Map the qubit **indices** on whom the :class:`ScheduledCircuit` instance is applied.

        Note:
            This method differs from :meth:`~ScheduledCircuit.map_to_qubits`
            because it changes the qubit indices, which requires to iterate the
            whole circuit and change every instruction target.

            This method should be used before combining several
            :class:`ScheduledCircuit` instances that are not aware of each
            other.

        Args:
            qubit_index_map: the map used to modify the qubit targets.
            inplace: if ``True``, perform the modification in place and return
                ``self``. Else, perform the modification in a copy and return
                the copy. Note that the runtime cost of this method should be
                the same independently of the value provided here.

        Returns:
            a modified instance of :class:`ScheduledCircuit` (a copy if
            ``inplace`` is ``True``, else ``self``).

        """
        mapped_final_qubits = QubitMap(
            {qubit_index_map[qi]: q for qi, q in self._qubit_map.items()}
        )
        mapped_moments: list[Moment] = [
            moment.with_mapped_qubit_indices(qubit_index_map) for moment in self._moments
        ]

        if inplace:
            self._qubit_map = mapped_final_qubits
            self._moments = mapped_moments
            return self
        else:
            return ScheduledCircuit(
                mapped_moments, self._schedule, mapped_final_qubits, _avoid_checks=True
            )

    def map_to_qubits(
        self,
        qubit_map: Callable[[GridQubit], GridQubit],
        inplace_qubit_map: bool = False,
    ) -> ScheduledCircuit:
        """Map the qubits the :class:`ScheduledCircuit` instance is applied on.

        Note:
            This method only changes the ``QUBIT_COORDS`` instructions at the
            beginning of the circuit. As such, it never has to iterate on the
            whole quantum circuit and so this method is very efficient.

        Warning:
            The underlying quantum circuit data-structure is never copied (even
            if ``inplace_qubit_map == True``), so the returned instance should be
            used with care, in particular if any method mutating the underlying
            circuit is called on ``self`` or the returned instance after calling
            that method.

        Args:
            qubit_map: the map used to modify the qubits.
            inplace_qubit_map: if True, replaces the qubit map directly in
                ``self`` and return ``self``. Else, create a new instance from
                ``self`` **without copying the underlying moments**, simply
                replacing the qubit map.

        Returns:
            an instance of :class:`ScheduledCircuit` with a new qubit map.

        """
        operand = self if inplace_qubit_map else copy(self)
        operand._qubit_map = operand._qubit_map.with_mapped_qubits(qubit_map)
        return operand

    def __copy__(self) -> ScheduledCircuit:
        return ScheduledCircuit(self._moments, self._schedule, self._qubit_map, _avoid_checks=True)

    def __deepcopy__(self, _: dict[Any, Any]) -> ScheduledCircuit:
        return ScheduledCircuit(
            deepcopy(self._moments),
            deepcopy(self._schedule),
            deepcopy(self._qubit_map),
            _avoid_checks=True,
        )

    @property
    def scheduled_moments(self) -> Iterator[tuple[int, Moment]]:
        """Yields ``stim.Circuit`` instances representing a moment with their computed schedule.

        This property yields all the scheduled moments.

        The yielded elements are sorted with respect to their schedule.

        """
        yield from zip(self._schedule, self._moments)

    @property
    def moments(self) -> Iterator[Moment]:
        """Iterator over the internal moments representing the computation."""
        yield from self._moments

    @property
    def qubits(self) -> frozenset[GridQubit]:
        """Set of qubits on which the circuit is applied."""
        return frozenset(self._qubit_map.qubits)

    def _get_moment_index_by_schedule(self, schedule: int) -> int | None:
        """Get the index of the moment scheduled at the provided schedule.

        Args:
            schedule: the schedule at which the Moment instance should be returned.
                If the schedule is negative, it is considered as an index from
                the end. For example, ``-1`` is the last schedule and ``-2`` is the
                ``last schedule - 1`` (which might not be the second to last
                schedule).

        Returns:
            the index of the :class:`~tqec.circuit.moment.Moment` instance
            scheduled at the provided schedule. If no
            :class:`~tqec.circuit.moment.Moment` instance is scheduled at the
            provided ``schedule``, ``None`` is returned.

        Raises:
            TQECError: if the provided calculated ``schedule`` is negative.

        """
        if not self._schedule:
            return None

        schedule = self._schedule[-1] + 1 + schedule if schedule < 0 else schedule
        if schedule < 0:
            raise TQECError(
                f"Trying to get the index of a Moment instance with a negative schedule {schedule}."
            )
        moment_index = next(
            (i for i, sched in enumerate(self._schedule) if sched == schedule), None
        )
        return moment_index

    def moment_at_schedule(self, schedule: int) -> Moment:
        """Get the :class:`~tqec.circuit.moment.Moment` instance scheduled at the provided schedule.

        Args:
            schedule: the schedule at which the :class:`~tqec.circuit.moment.Moment`
                instance should be returned. If the ``schedule`` is negative, it
                is considered as an index from the end. For example, ``-1`` is the
                last schedule and ``-2`` is the ``last schedule - 1`` (which
                might not be the second to last schedule).

        Raises:
            TQECError: if no moment exist at the provided ``schedule``.

        """
        moment_index = self._get_moment_index_by_schedule(schedule)
        if moment_index is None:
            raise TQECError(f"No Moment instance scheduled at the provided schedule {schedule}.")
        return self._moments[moment_index]

    def append_new_moment(self, moment: Moment) -> None:
        """Schedule the provided :class:`.Moment` instance at the end of the circuit.

        The new schedule will be the last schedule plus one.

        Args:
            moment: the moment to schedule.

        """
        # By default, we cannot assume that self._schedule contains an entry, so
        # we insert at the first moment.
        schedule = Schedule._INITIAL_SCHEDULE
        # If it turns out that we have at least one scheduled moment, then
        # insert just after.
        if self._schedule:
            schedule = self._schedule[-1] + 1
        self.add_to_schedule_index(schedule, moment)

    def add_to_schedule_index(self, schedule: int, moment: Moment) -> None:
        """Add the operations contained in the provided ``moment`` to the provided schedule.

        Args:
            schedule: schedule at which operations in ``moment`` should be added.
                If the schedule is negative, it is considered as an index from
                the end. For example, ``-1`` is the last schedule and ``-2`` is the
                ``last schedule - 1`` (which might not be the second to last
                schedule).
            moment: operations that should be added.

        """
        moment_index = self._get_moment_index_by_schedule(schedule)
        if moment_index is None:
            # We have to insert a new schedule and a new Moment.
            insertion_index = bisect.bisect_left(self._schedule, schedule)
            self._schedule.insert(insertion_index, schedule)
            self._moments.insert(insertion_index, moment)
        else:
            # Else, the schedule already exists, in which case we just need to
            # add the operations to an existing moment. Note that this might
            # fail if two instructions overlap.
            self._moments[moment_index] += moment

    def append_observable(self, index: int, targets: Sequence[stim.GateTarget]) -> None:
        """Append an ``OBSERVABLE_INCLUDE`` instruction to the last moment.

        Args:
            index: index of the observable to append measurement records to.
            targets: measurement records forming (part of) the observable.

        """
        self.append_annotation(stim.CircuitInstruction("OBSERVABLE_INCLUDE", targets, [index]))

    def append_annotation(self, instruction: stim.CircuitInstruction) -> None:
        """Append an annotation to the last moment.

        Args:
            instruction: an annotation that will be added to the last moment of
                ``self``.

        Raises:
            TQECError: if the provided instruction is not an annotation.

        """
        if not is_annotation_instruction(instruction):
            raise TQECError(
                "The provided instruction is not an annotation, which is "
                "disallowed by the append_annotation method."
            )
        self._moments[-1].append_annotation(instruction)

    @property
    def num_measurements(self) -> int:
        """Number of measurements in the represented computation."""
        return sum(m.num_measurements for m in self._moments)

    def filter_by_qubits(self, qubits_to_keep: Iterable[GridQubit]) -> ScheduledCircuit:
        """Filter the circuit to keep only the instructions that are applied on the provided qubits.

        If an instruction is applied on a qubit that is not in the provided list, it is removed.

        After filtering, the empty moments as well as the corresponding schedules
        are removed.

        Args:
            qubits_to_keep: the qubits to keep in the circuit.

        Returns:
            a new instance of :class:`ScheduledCircuit` with the filtered
            circuit and schedules.

        """
        qubits_indices_to_keep = frozenset(
            self._qubit_map.q2i[q] for q in qubits_to_keep if q in self.qubits
        )
        filtered_moments: list[Moment] = []
        filtered_schedule: list[int] = []
        for schedule, moment in self.scheduled_moments:
            filtered_moment = moment.filter_by_qubits(qubits_indices_to_keep)
            if filtered_moment.is_empty:
                continue
            filtered_moments.append(filtered_moment)
            filtered_schedule.append(schedule)
        qubit_map = self._qubit_map.filter_by_qubits(qubits_to_keep)
        filtered_circuit = ScheduledCircuit(
            filtered_moments, Schedule(filtered_schedule), qubit_map, _avoid_checks=True
        )
        # The qubit indices may not be contiguous anymore, so we need to remap them.
        indices_map = {oi: ni for ni, oi in enumerate(qubit_map.indices)}
        return filtered_circuit.map_qubit_indices(indices_map)

    @property
    def qubit_map(self) -> QubitMap:
        """Qubit map of the circuit."""
        return self._qubit_map

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ScheduledCircuit)
            and self._schedule == other._schedule
            and self._qubit_map == other._qubit_map
            and self._moments == other._moments
        )

    def __hash__(self) -> int:
        raise NotImplementedError(f"Cannot hash efficiently a {type(self).__name__}.")

    def is_empty(self) -> bool:
        """Return ``True`` if ``self`` represents an empty circuit.

        Warning:
            an empty circuit is defined as a circuit containing no instructions.
            ``QUBIT_COORDINATES`` instructions are ignored by this method (i.e., a circuit with only
            ``QUBIT_COORDINATES`` instructions is considered empty), but other annotations are taken
            into account (i.e., a circuit with a ``DETECTOR`` or ``SHIFT_COORDS`` instruction will
            not be considered empty).

        """
        return all(m.is_empty for m in self._moments)

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the circuit.

        Returns:
            a dictionary with the keys ``moments``, ``schedule`` and
            ``qubit_map`` and their corresponding values.

        """
        return {
            "moments": [m.to_dict() for m in self._moments],
            "schedule": self._schedule.schedule,
            "qubit_map": self._qubit_map.to_dict(),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ScheduledCircuit:
        """Return a circuit from its dictionary representation.

        Args:
            data: dictionary with the keys ``moments``, ``schedule`` and
                ``qubit_map``.

        """
        moments = [Moment.from_dict(m) for m in data["moments"]]
        schedule = Schedule(data["schedule"])
        qubit_map = QubitMap.from_dict(data["qubit_map"])
        return ScheduledCircuit(moments, schedule, qubit_map, _avoid_checks=True)
