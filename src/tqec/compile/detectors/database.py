from __future__ import annotations

import hashlib
import json
import pickle
import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any, ClassVar, Final

import numpy
import semver

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
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Shift2D

CURRENT_DATABASE_VERSION: Final[semver.Version] = semver.Version(1, 0, 0)


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
            raise TQECError(
                "DetectorDatabaseKey can only store an equal number of "
                f"subtemplates and plaquettes. Got {len(self.subtemplates)} "
                f"subtemplates and {len(self.plaquettes_by_timestep)} plaquettes."
            )

    @property
    def num_timeslices(self) -> int:
        return len(self.subtemplates)

    @cached_property
    def plaquette_names(self) -> tuple[tuple[tuple[str, ...], ...], ...]:
        """Cached property returning a representation of the current situation with plaquette names.

        Returns:
            Nested tuples such that
            ``ret[t][y][x] == self.plaquettes_by_timestep[t][self.subtemplates[t][y, x]].name``.

            The returned object can be iterated on using:

            .. code:: python

                for t, names in enumerate(self.plaquette_names):
                    subtemplate = self.subtemplates[t]
                    plaquettes = self.plaquettes_by_timestep[t]
                    for y, names_row in enumerate(names):
                        for x, name in enumerate(names_row):
                            plaquette: Plaquette = plaquettes[subtemplate[y, x]]
                            assert name == plaquette.name

        """
        return tuple(
            tuple(tuple(plaquettes[pi].name for pi in row) for row in st)
            for st, plaquettes in zip(self.subtemplates, self.plaquettes_by_timestep)
        )

    @cached_property
    def reliable_hash(self) -> int:
        """Return a hash of ``self`` that is guaranteed to be constant.

        Python's ``hash`` is not guaranteed to be constant across Python versions, OSes and
        executions. In particular, strings hash will not be repeatable across different Python
        executable calls. The following line should return different values at each call:

        .. code:: bash

            python -c 'print(hash("Hello world"))'

        For example, here are the results obtained after calling that line 3 times on my machine:

        - ``2656127643635015930``
        - ``1413792191058799258``
        - ``8731178165517315210``

        This is an issue for the detector database as we would like it to be reproducible. Else,
        reusing an existing database will always fail because keys will have a different hash,
        hence re-computing detectors at each call and growing the database indefinitely.

        This method implements a reliable hash that should be constant no matter the context
        (different Python calls, different OS, different version of Python, ...).
        """
        hasher = hashlib.md5()
        for timeslice in self.plaquette_names:
            for row in timeslice:
                for name in row:
                    hasher.update(name.encode())
        return int(hasher.hexdigest(), 16)

    def __hash__(self) -> int:
        return self.reliable_hash

    def __eq__(self, rhs: object) -> bool:
        return isinstance(rhs, _DetectorDatabaseKey) and self.plaquette_names == rhs.plaquette_names

    def circuit(self, plaquette_increments: Shift2D) -> ScheduledCircuit:
        """Get the `stim.Circuit` instance represented by `self`.

        Args:
            plaquette_increments: displacement between each plaquette origin.

        Returns:
            `stim.Circuit` instance represented by `self`.

        """
        circuits, qubit_map = relabel_circuits_qubit_indices(
            [
                generate_circuit_from_instantiation(subtemplate, plaquettes, plaquette_increments)
                for subtemplate, plaquettes in zip(self.subtemplates, self.plaquettes_by_timestep)
            ]
        )
        moments: list[Moment] = list(circuits[0].moments)
        schedule: Schedule = circuits[0].schedule
        for circuit in circuits[1:]:
            moments.extend(circuit.moments)
            schedule.append_schedule(circuit.schedule)
        return ScheduledCircuit(moments, schedule, qubit_map)

    def to_dict(self, plaquettes_to_indices: dict[Plaquette, int]) -> dict[str, Any]:
        """Return a dictionary representation of the key.

        Args:
            plaquettes_to_indices: mapping from each :class:`Plaquette` to its
                index in the list of unique plaquettes. Each plaquette is
                represented by its index in the list of unique
                plaquettes to save space.

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
        plaquettes: Sequence[Plaquette],
    ) -> _DetectorDatabaseKey:
        """Return a key from its dictionary representation.

        Args:
            data: dictionary with the keys ``subtemplates`` and
                ``plaquettes_by_timestep``.
            plaquettes: list of :class:`Plaquette` instances to use to build the
                :class:`Plaquettes` instances. Each plaquette is represented by
                its index in the list of unique plaquettes to save space.

        Returns:
            a new instance of :class:`_DetectorDatabaseKey` with the provided
            ``subtemplates`` and ``plaquettes_by_timestep``.

        """
        subtemplates = [numpy.array(st) for st in data["subtemplates"]]
        plaquettes_by_timestep = [
            Plaquettes.from_dict(p, plaquettes) for p in data["plaquettes_by_timestep"]
        ]
        return _DetectorDatabaseKey(subtemplates, plaquettes_by_timestep)


class _DetectorDatabaseIO:
    @staticmethod
    def _handle_load_error(filepath: Path, exception: Exception, ext: str) -> DetectorDatabase:
        moving_location = filepath.parent / f"faulty_database_{hash(exception)}.{ext}"
        warnings.warn(
            f"Error ({type(exception).__name__}) "
            f"when reading the database at {filepath}: {exception}. "
            f"Moving the database to {moving_location} and returning an empty database."
        )
        filepath.rename(moving_location)
        return DetectorDatabase()

    @staticmethod
    def from_pickle_file(filepath: Path) -> DetectorDatabase:
        try:
            with open(filepath, "rb") as f:
                database = pickle.load(f)
        except Exception as e:
            return _DetectorDatabaseIO._handle_load_error(filepath, e, "pkl")

        if not isinstance(database, DetectorDatabase):
            raise TQECError(
                f"Found the Python type {type(database).__name__} in the "
                f"provided file but {type(DetectorDatabase).__name__} was "
                "expected."
            )
        return database

    @staticmethod
    def from_json_file(filepath: Path) -> DetectorDatabase:
        try:
            with open(filepath) as f:
                data = json.load(f)
                database = DetectorDatabase.from_dict(data)
        except Exception as e:
            return _DetectorDatabaseIO._handle_load_error(filepath, e, "json")

        if not isinstance(database, DetectorDatabase):
            raise TQECError(
                f"Found the Python type {type(database).__name__} in the "
                f"provided file but {type(DetectorDatabase).__name__} was "
                "expected."
            )
        return database

    @staticmethod
    def to_pickle_file(filepath: Path, database: DetectorDatabase) -> None:
        with open(filepath, "wb") as f:
            pickle.dump(database, f)

    @staticmethod
    def to_json_file(filepath: Path, database: DetectorDatabase) -> None:
        with open(filepath, "w") as f:
            json.dump(database.to_dict(), f)


def _get_database_format(filepath: Path) -> str:
    suffix = filepath.suffix.lower()
    if suffix in {".pkl", ".pickle"}:
        return "pickle"
    if suffix in {".json"}:
        return "json"
    raise TQECError(
        f"Could not infer the database format from the provided filepath ('{filepath}'). "
        "Supported formats are:\n  -" + "\n  -".join(DetectorDatabase._WRITERS.keys())
    )


class DetectorDatabase:
    version: semver.Version = semver.Version(0, 0, 0)

    _READERS: ClassVar[Mapping[str, Callable[[Path], DetectorDatabase]]] = {
        "pickle": _DetectorDatabaseIO.from_pickle_file,
        "json": _DetectorDatabaseIO.from_json_file,
    }
    _WRITERS: ClassVar[Mapping[str, Callable[[Path, DetectorDatabase], None]]] = {
        "pickle": _DetectorDatabaseIO.to_pickle_file,
        "json": _DetectorDatabaseIO.to_json_file,
    }

    def __init__(
        self,
        mapping: dict[_DetectorDatabaseKey, frozenset[Detector]] | None = None,
        frozen: bool = False,
    ):
        """Store a mapping from "situations" to the corresponding detectors.

        This class aims at storing efficiently a set of "situations" in which the
        corresponding detectors are known and do not have to be re-computed.

        In this class, a "situation" is described by :class:`_DetectorDatabaseKey`
        and correspond to a spatially and temporally local piece of a larger
        computation.

        The version number should be manually updated when code is pushed which makes old
        instances of the database incompatible with newly generated instances.
        Guidance on when to change `a` (major) or `b` (minor) in the `a.b` version number:
        - MAJOR when the format of the file changes (i.e. when the attributes of
        ``DetectorDatabase`` change),
        - MINOR when the content of the database is invalidated (e.g. by changing a plaquette
        implementation without changing its name).

        Old databases generated prior to the introduction of a version attribute will be
        loaded with the default value of .version, without passing through __init__,
        ie (0,0,0).

        """
        if mapping is None:
            mapping = dict()
        self.mapping = mapping
        self.frozen = frozen
        self.version = CURRENT_DATABASE_VERSION

    def add_situation(
        self,
        subtemplates: Sequence[SubTemplateType],
        plaquettes_by_timestep: Sequence[Plaquettes],
        detectors: frozenset[Detector] | Detector,
    ) -> None:
        """Add a new situation to the database.

        Args:
            subtemplates: a sequence of 2-dimensional arrays of integers
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
            TQECError: if this method is called and `self.frozen`.

        """
        if self.frozen:
            raise TQECError("Cannot add a situation to a frozen database.")
        key = _DetectorDatabaseKey(subtemplates, plaquettes_by_timestep)
        self.mapping[key] = frozenset([detectors]) if isinstance(detectors, Detector) else detectors

    def remove_situation(
        self,
        subtemplates: Sequence[SubTemplateType],
        plaquettes_by_timestep: Sequence[Plaquettes],
    ) -> None:
        """Remove an existing situation from the database.

        Args:
            subtemplates: a sequence of 2-dimensional arrays of integers
                representing the sub-template(s). Each entry corresponds to one
                QEC round.
            plaquettes_by_timestep: a list of :class:`Plaquettes`, each
                :class:`Plaquettes` entry storing enough :class:`Plaquette`
                instances to generate a circuit from corresponding entry in
                `self.subtemplates` and corresponding to one QEC round.

        Raises:
            TQECError: if this method is called and `self.frozen`.

        """
        if self.frozen:
            raise TQECError("Cannot remove a situation to a frozen database.")
        key = _DetectorDatabaseKey(subtemplates, plaquettes_by_timestep)
        del self.mapping[key]

    def get_detectors(
        self,
        subtemplates: Sequence[SubTemplateType],
        plaquettes_by_timestep: Sequence[Plaquettes],
    ) -> frozenset[Detector] | None:
        """Return the detectors associated with the provided situation.

        Args:
            subtemplates: a sequence of 2-dimensional arrays of integers
                representing the sub-template(s). Each entry corresponds to one
                QEC round.
            plaquettes_by_timestep: a list of :class:`Plaquettes`, each
                :class:`Plaquettes` entry storing enough :class:`Plaquette`
                instances to generate a circuit from corresponding entry in
                `self.subtemplates` and corresponding to one QEC round.

        Returns:
            detectors associated with the provided situation or `None` if the
            situation is not in the database.

        """
        key = _DetectorDatabaseKey(subtemplates, plaquettes_by_timestep)
        return self.mapping.get(key)

    def freeze(self) -> None:
        """Make ``self`` read-only."""
        self.frozen = True

    def unfreeze(self) -> None:
        """Make ``self`` writable."""
        self.frozen = False

    def to_crumble_urls(self, plaquette_increments: Shift2D = Shift2D(2, 2)) -> list[str]:
        """Return a URL pointing to https://algassert.com/crumble for each of the stored situations.

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

    def to_file(self, filepath: Path) -> None:
        """Save the database to a file.

        Args:
            filepath: path to the file where the database should be saved.

        """
        if not filepath.parent.exists():
            filepath.parent.mkdir(parents=True)
        format = _get_database_format(filepath)
        DetectorDatabase._WRITERS[format](filepath, self)

    @staticmethod
    def from_file(filepath: Path) -> DetectorDatabase:
        """Initialise a new instance from a file.

        Args:
            filepath: path to a file where a :class:`.DetectorDatabase` instance has been saved.

        Returns:
            a new :class:`.DetectorDatabase` instance read from the provided ``filepath``.

        """
        if not filepath.exists():
            raise TQECError(
                f"Could not read the database: the provided filepath ('{filepath}') does not exist "
                "on disk."
            )
        format = _get_database_format(filepath)
        return DetectorDatabase._READERS[format](filepath)
