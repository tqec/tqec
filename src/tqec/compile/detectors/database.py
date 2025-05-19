from __future__ import annotations

import hashlib
import json
import pickle
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any, Literal, Sequence

import numpy

from tqec.circuit.measurement_map import MeasurementRecordsMap
from tqec.circuit.moment import Moment
from tqec.circuit.schedule import (
    Schedule,
    ScheduledCircuit,
    relabel_circuits_qubit_indices,
)
from tqec.compile.detectors.detector import Detector
from tqec.compile.generation import generate_circuit_from_instantiation
from tqec.plaquette.plaquette import Plaquette, Plaquettes
from tqec.templates.subtemplates import SubTemplateType
from tqec.utils.exceptions import TQECException
from tqec.utils.position import Shift2D


@dataclass(frozen=True)
class _DetectorDatabaseKey:
    """Immutable type used as a key in the database of detectors.

    This class represents a "situation" for which we might be able to compute
    several detectors. Its purpose of existence is to provide sensible
    `__hash__` and `__eq__` operations in order to be able to use a "situation"
    as a `dict` key.

    Attributes:
        subtemplates: a sequence of 2-dimensional arrays of integers representing
            the sub-template(s). Each entry corresponds to one QEC round.
        plaquettes_by_timestep: a list of :class:`Plaquettes`, each
            :class:`Plaquettes` entry storing enough :class:`Plaquette`
            instances to generate a circuit from corresponding entry in
            `self.subtemplates` and corresponding to one QEC round.

    ## Implementation details

    This class uses a surjective representation to compare (`__eq__`) and hash
    (`__hash__`) its instances. This representation is computed and cached using
    the :meth:`_DetectorDatabaseKey.plaquette_names` property that basically
    uses the provided subtemplates to build a nested tuple data-structure with
    the same shape as `self.subtemplates` (3 dimensions, the first one being the
    number of time steps, the next 2 ones being of odd and equal size and
    depending on the radius used to build subtemplates) storing in each of its
    entries the corresponding plaquette name.

    This intermediate data-structure is not the most memory efficient one, but
    it has the advantage of being easy to construct, trivially invariant to
    plaquette re-indexing and easy to hash (with some care to NOT use Python's
    default `hash` due to its absence of stability across different runs).
    """

    subtemplates: Sequence[SubTemplateType]
    plaquettes_by_timestep: Sequence[Plaquettes]

    def __post_init__(self) -> None:
        if len(self.subtemplates) != len(self.plaquettes_by_timestep):
            raise TQECException(
                "DetectorDatabaseKey can only store an equal number of "
                f"subtemplates and plaquettes. Got {len(self.subtemplates)} "
                f"subtemplates and {len(self.plaquettes_by_timestep)} plaquettes."
            )

    @property
    def num_timeslices(self) -> int:
        return len(self.subtemplates)

    @cached_property
    def plaquette_names(self) -> tuple[tuple[tuple[str, ...], ...], ...]:
        """Cached property that returns nested tuples such that `ret[t][y][x]
        == self.plaquettes_by_timestep[t][self.subtemplates[t][y, x]].name`.

        The returned object can be iterated on using:

        ```py
        for t, names in enumerate(self.plaquette_names):
            subtemplate = self.subtemplates[t]
            plaquettes = self.plaquettes_by_timestep[t]
            for y, names_row in enumerate(names):
                for x, name in enumerate(names_row):
                    plaquette: Plaquette = plaquettes[subtemplate[y, x]]
                    assert name == plaquette.name
        ```
        """
        return tuple(
            tuple(tuple(plaquettes[pi].name for pi in row) for row in st)
            for st, plaquettes in zip(self.subtemplates, self.plaquettes_by_timestep)
        )

    @cached_property
    def reliable_hash(self) -> int:
        """Returns a hash of `self` that is guaranteed to be constant across
        Python versions, OSes and executions."""
        hasher = hashlib.md5()
        for timeslice in self.plaquette_names:
            for row in timeslice:
                for name in row:
                    hasher.update(name.encode())
        return int(hasher.hexdigest(), 16)

    def __hash__(self) -> int:
        return self.reliable_hash

    def __eq__(self, rhs: object) -> bool:
        return (
            isinstance(rhs, _DetectorDatabaseKey)
            and self.plaquette_names == rhs.plaquette_names
        )

    def circuit(self, plaquette_increments: Shift2D) -> ScheduledCircuit:
        """Get the `stim.Circuit` instance represented by `self`.

        Args:
            plaquette_increments: displacement between each plaquette origin.

        Returns:
            `stim.Circuit` instance represented by `self`.
        """
        circuits, qubit_map = relabel_circuits_qubit_indices(
            [
                generate_circuit_from_instantiation(
                    subtemplate, plaquettes, plaquette_increments
                )
                for subtemplate, plaquettes in zip(
                    self.subtemplates, self.plaquettes_by_timestep
                )
            ]
        )
        moments: list[Moment] = list(circuits[0].moments)
        schedule: Schedule = circuits[0].schedule
        for circuit in circuits[1:]:
            moments.extend(circuit.moments)
            schedule.append_schedule(circuit.schedule)
        return ScheduledCircuit(moments, schedule, qubit_map)

    def to_dict(
        self, plaquettes_to_indices: dict[Plaquette, int] | None = None
    ) -> dict[str, Any]:
        """Return a dictionary representation of the key.

        Returns:
            a dictionary with the keys ``subtemplates`` and
            ``plaquettes_by_timestep`` and their corresponding values.
        """
        return {
            "subtemplates": [st.tolist() for st in self.subtemplates],
            "plaquettes_by_timestep": [
                p.to_dict(plaquettes_to_indices) for p in self.plaquettes_by_timestep
            ],
        }

    @staticmethod
    def from_dict(
        data: dict[str, Any],
        plaquettes: Sequence[Plaquette] | None = None,
    ) -> _DetectorDatabaseKey:
        """Return a key from its dictionary representation.

        Args:
            data: dictionary with the keys ``subtemplates`` and
                ``plaquettes_by_timestep``.
            plaquettes: list of :class:`Plaquette` instances to use to build the
                :class:`Plaquettes` instances. If `None`, the function will
                create a new list of :class:`Plaquette` instances.

        Returns:
            a new instance of :class:`_DetectorDatabaseKey` with the provided
            ``subtemplates`` and ``plaquettes_by_timestep``.
        """
        subtemplates = [numpy.array(st) for st in data["subtemplates"]]
        plaquettes_by_timestep = [
            Plaquettes.from_dict(p, plaquettes) for p in data["plaquettes_by_timestep"]
        ]
        return _DetectorDatabaseKey(subtemplates, plaquettes_by_timestep)


@dataclass
class DetectorDatabase:
    """Store a mapping from "situations" to the corresponding detectors.

    This class aims at storing efficiently a set of "situations" in which the
    corresponding detectors are known and do not have to be re-computed.

    In this class, a "situation" is described by :class:`_DetectorDatabaseKey`
    and correspond to a spatially and temporally local piece of a larger
    computation.
    """

    mapping: dict[_DetectorDatabaseKey, frozenset[Detector]] = field(
        default_factory=dict
    )
    frozen: bool = False

    def add_situation(
        self,
        subtemplates: Sequence[SubTemplateType],
        plaquettes_by_timestep: Sequence[Plaquettes],
        detectors: frozenset[Detector] | Detector,
    ) -> None:
        """Add a new situation to the database.

        Args:
            subtemplate: a sequence of 2-dimensional arrays of integers
                representing the sub-template(s). Each entry corresponds to one
                QEC round.
            plaquettes_by_timestep: a list of :class:`Plaquettes`, each
                :class:`Plaquettes` entry storing enough :class:`Plaquette`
                instances to generate a circuit from corresponding entry in
                `self.subtemplates` and corresponding to one QEC round.
            detectors: computed detectors that should be stored in the database.
                The coordinates used by the :class:`Measurement` instances stored
                in each entry should be relative to the top-left qubit of the
                top-left plaquette in the provided `subtemplates`.

        Raises:
            TQECException: if this method is called and `self.frozen`.
        """
        if self.frozen:
            raise TQECException("Cannot add a situation to a frozen database.")
        key = _DetectorDatabaseKey(subtemplates, plaquettes_by_timestep)
        self.mapping[key] = (
            frozenset([detectors]) if isinstance(detectors, Detector) else detectors
        )

    def remove_situation(
        self,
        subtemplates: Sequence[SubTemplateType],
        plaquettes_by_timestep: Sequence[Plaquettes],
    ) -> None:
        """Remove an existing situation from the database.

        Args:
            subtemplate: a sequence of 2-dimensional arrays of integers
                representing the sub-template(s). Each entry corresponds to one
                QEC round.
            plaquettes_by_timestep: a list of :class:`Plaquettes`, each
                :class:`Plaquettes` entry storing enough :class:`Plaquette`
                instances to generate a circuit from corresponding entry in
                `self.subtemplates` and corresponding to one QEC round.

        Raises:
            TQECException: if this method is called and `self.frozen`.
        """
        if self.frozen:
            raise TQECException("Cannot remove a situation to a frozen database.")
        key = _DetectorDatabaseKey(subtemplates, plaquettes_by_timestep)
        del self.mapping[key]

    def get_detectors(
        self,
        subtemplates: Sequence[SubTemplateType],
        plaquettes_by_timestep: Sequence[Plaquettes],
    ) -> frozenset[Detector] | None:
        """Return the detectors associated with the provided situation or
        `None` if the situation is not in the database.

        Args:
            subtemplate: a sequence of 2-dimensional arrays of integers
                representing the sub-template(s). Each entry corresponds to one
                QEC round.
            plaquettes_by_timestep: a list of :class:`Plaquettes`, each
                :class:`Plaquettes` entry storing enough :class:`Plaquette`
                instances to generate a circuit from corresponding entry in
                `self.subtemplates` and corresponding to one QEC round.
            detectors: computed detectors that should be stored in the database.

        Returns:
            detectors associated with the provided situation or `None` if the
            situation is not in the database.
        """
        key = _DetectorDatabaseKey(subtemplates, plaquettes_by_timestep)
        return self.mapping.get(key)

    def freeze(self) -> None:
        self.frozen = True

    def unfreeze(self) -> None:
        self.frozen = False

    def to_crumble_urls(
        self, plaquette_increments: Shift2D = Shift2D(2, 2)
    ) -> list[str]:
        """Returns one URL pointing to https://algassert.com/crumble for each of
        the registered situations.

        Args:
            plaquette_increments: increments between two :class:`Plaquette`
                origins. Default to `Displacement(2, 2)` which is the expected
                value for surface code.

        Returns:
            a list of Crumble URLs, each one representing a situation stored in
            `self`.
        """
        urls: list[str] = []
        for key, detectors in self.mapping.items():
            circuit = key.circuit(plaquette_increments)
            rec_map = MeasurementRecordsMap.from_scheduled_circuit(circuit)
            for detector in detectors:
                circuit.append_annotation(detector.to_instruction(rec_map))
            urls.append(circuit.get_circuit().to_crumble_url())
        return urls

    def __len__(self) -> int:
        return len(self.mapping)

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the database.

        Returns:
            a dictionary with the keys ``mapping`` and ``frozen`` and their
            corresponding values.
        """
        # First obtain the unique plaquettes
        plaquettes_set: set[Plaquette] = set()
        for key in self.mapping:
            for p in key.plaquettes_by_timestep:
                if p.collection.default_value is not None:
                    plaquettes_set.add(p.collection.default_value)
                plaquettes_set.update(p.collection.values())
        uniq_plaquettes: Sequence[Plaquette] = list(plaquettes_set)
        # Then create a mapping from each plaquette to its index
        plaquettes_to_indices = {p: i for i, p in enumerate(uniq_plaquettes)}
        return {
            "mapping": [
                [
                    key.to_dict(plaquettes_to_indices=plaquettes_to_indices),
                    [d.to_dict() for d in detectors],
                ]
                for key, detectors in self.mapping.items()
            ],
            "frozen": self.frozen,
            "uniq_plaquettes": [p.to_dict() for p in uniq_plaquettes],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> DetectorDatabase:
        """Return a database from its dictionary representation.

        Args:
            data: dictionary with the keys ``mapping`` and ``frozen``.

        Returns:
            a new instance of :class:`DetectorDatabase` with the provided
            ``mapping`` and ``frozen``.
        """
        uniq_plaquettes = [Plaquette.from_dict(p) for p in data["uniq_plaquettes"]]
        mapping = {
            _DetectorDatabaseKey.from_dict(key, plaquettes=uniq_plaquettes): frozenset(
                Detector.from_dict(d) for d in detectors
            )
            for key, detectors in data["mapping"]
        }
        return DetectorDatabase(mapping, data["frozen"])

    def to_file(
        self, filepath: Path, format: Literal["pickle", "json"] = "pickle"
    ) -> None:
        """Save the database to a file.

        Args:
            filepath: path to the file where the database should be saved.
            format: format to use to save the database. Currently only
                "pickle" and "json" are supported.
        """
        if not filepath.parent.exists():
            filepath.parent.mkdir()
        if format == "pickle":
            with open(filepath, "wb") as f:
                pickle.dump(self, f)
        else:
            filepath = filepath.with_suffix(".json")
            with open(filepath, "w") as f:
                json.dump(self.to_dict(), f)

    @staticmethod
    def from_file(
        filepath: Path, format: Literal["pickle", "json"] = "pickle"
    ) -> DetectorDatabase:
        if format == "pickle":
            with open(filepath, "rb") as f:
                database = pickle.load(f)
        else:
            with open(filepath) as f:
                data = json.load(f)
                database = DetectorDatabase.from_dict(data)
        if not isinstance(database, DetectorDatabase):
            raise TQECException(
                f"Found the Python type {type(database).__name__} in the "
                f"provided file but {type(DetectorDatabase).__name__} was "
                "expected."
            )
        return database
