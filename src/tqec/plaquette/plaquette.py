from __future__ import annotations

import hashlib
import warnings
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, cast

import stim

from tqec.circuit.qubit import GridQubit
from tqec.circuit.schedule import ScheduledCircuit
from tqec.plaquette.debug import PlaquetteDebugInformation
from tqec.plaquette.enums import PlaquetteOrientation
from tqec.plaquette.qubit import PlaquetteQubits
from tqec.utils.exceptions import TQECError, TQECWarning
from tqec.utils.frozendefaultdict import FrozenDefaultDict
from tqec.utils.position import PhysicalQubitPosition2D


@dataclass(frozen=True)
class Plaquette:
    """Represent a QEC plaquette.

    This class stores qubits in the plaquette local coordinate system and a
    scheduled circuit that should be applied on those qubits to perform the
    QEC experiment.

    By convention, the local plaquette coordinate system is composed of a
    X-axis pointing to the right and a Y-axis pointing down.

    Attributes:
        name: a unique name for the plaquette. This field is used to compare
            plaquettes efficiently (two :class:`Plaquette` instances are
            considered equal if and only if their names are the same) as well as
            computing a hash value for any plaquette instance. Finally, the name
            is used to represent a :class:`Plaquette` instance as a string.
        qubits: qubits used by the plaquette circuit, given in the local
            plaquette coordinate system.
        circuit: scheduled quantum circuit implementing the computation that
            the plaquette should represent.
        mergeable_instructions: a set of instructions that can
            be merged. This is useful when merging several plaquettes'
            circuits together to remove duplicate instructions.

    Raises:
        TQECError: if the provided `circuit` uses qubits not listed in
            `qubits`.

    """

    name: str
    qubits: PlaquetteQubits
    circuit: ScheduledCircuit
    mergeable_instructions: frozenset[str] = field(default_factory=frozenset)
    debug_information: PlaquetteDebugInformation = field(default_factory=PlaquetteDebugInformation)

    def __post_init__(self) -> None:
        plaquette_qubits = set(self.qubits)
        circuit_qubits = set(self.circuit.qubits)
        if not circuit_qubits.issubset(plaquette_qubits):
            wrong_qubits = circuit_qubits.difference(plaquette_qubits)
            raise TQECError(
                f"The following qubits ({wrong_qubits}) are in the provided circuit "
                "but not in the provided list of qubits."
            )

    @property
    def origin(self) -> PhysicalQubitPosition2D:
        """Return the plaquette origin.

        By definition, for the moment, the plaquette origin is always ``(0, 0)``.

        """
        return PhysicalQubitPosition2D(0, 0)

    def __eq__(self, rhs: object) -> bool:
        return isinstance(rhs, Plaquette) and self.name == rhs.name

    def __hash__(self) -> int:
        return hash(self.name)

    def __str__(self) -> str:
        return self.name  # pragma: no cover

    def project_on_data_qubit_indices(self, data_qubits_indices: list[int]) -> Plaquette:
        """Project the plaquette on the provided qubit indices.

        This method is useful for deriving a boundary plaquette from a integral
        plaquette.

        Args:
            data_qubits_indices: data-qubit indices that will be kept in the returned plaquette.

        Returns:
            A new plaquette with projected qubits and circuit. The qubits are
            updated to only keep the provided ``data_qubits_indices``. The
            circuit is also updated to only use the kept qubits and empty
            moments with the corresponding schedules are removed.

        """
        kept_qubits = [
            q for i, q in self.qubits.data_qubits_with_indices if i in data_qubits_indices
        ]
        return self.project_on_data_qubits(kept_qubits)

    def project_on_data_qubits(self, data_qubits: list[GridQubit]) -> Plaquette:
        """Project the plaquette on the provided qubits.

        This method is useful for deriving a boundary plaquette from a integral
        plaquette.

        Args:
            data_qubits: qubits that will be kept in the returned plaquette.

        Returns:
            A new plaquette with projected qubits and circuit. The qubits are
            updated to only keep the provided ``data_qubits``. The circuit is
            also updated to only use the kept qubits and empty moments with the
            corresponding schedules are removed.

        """
        removed_data_qubit_indices = [
            i for i, q in self.qubits.data_qubits_with_indices if q not in data_qubits
        ]
        new_plaquette_qubits = PlaquetteQubits(data_qubits, self.qubits.syndrome_qubits)
        new_scheduled_circuit = self.circuit.filter_by_qubits(new_plaquette_qubits.all_qubits)
        debug_info = self.debug_information
        if debug_info is not None:
            debug_info = debug_info.with_data_qubits_removed(removed_data_qubit_indices)

        return Plaquette(
            f"{self.name}_" + "_".join(map(str, removed_data_qubit_indices)),
            new_plaquette_qubits,
            new_scheduled_circuit,
            self.mergeable_instructions,
            debug_info,
        )

    def project_on_boundary(self, projected_orientation: PlaquetteOrientation) -> Plaquette:
        """Project the plaquette on a boundary and return the projected version.

        This method is useful for deriving a boundary plaquette from a integral
        plaquette.

        Args:
            projected_orientation: the orientation of the plaquette after the
                projection.

        Returns:
            A new plaquette with projected qubits and circuit. The qubits are
            updated to only keep the qubits on the side complementary to the
            provided orientation. The circuit is also updated to only use the
            kept qubits and empty moments with the corresponding schedules are
            removed.

        """
        kept_data_qubits = self.qubits.get_qubits_on_side(projected_orientation.to_plaquette_side())
        new_plaquette_qubits = PlaquetteQubits(kept_data_qubits, self.qubits.syndrome_qubits)
        new_scheduled_circuit = self.circuit.filter_by_qubits(new_plaquette_qubits.all_qubits)
        debug_info = self.debug_information.project_on_boundary(projected_orientation)
        return Plaquette(
            f"{self.name}_{projected_orientation.name}",
            new_plaquette_qubits,
            new_scheduled_circuit,
            self.mergeable_instructions,
            debug_info,
        )

    def reliable_hash(self) -> int:
        """Return a hash of ``self`` that is replicable across OSes and Python runs.

        The default ``hash`` function from Python is not guaranteed to always give the same value
        from the same input. In particular, with CPython, ``str`` instances are hashed with an
        additional salt that is randomly picked at each call to the Python executable.

        This is an issue when trying to store a dictionary involving a plaquette as key and re-use
        it in subsequent runs or on other machines / OSes.

        """
        return int(hashlib.md5(self.name.encode()).hexdigest(), 16)  # pragma: no cover

    @property
    def num_measurements(self) -> int:
        """Return the number of measurements performed in the circuit representing ``self``."""
        return self.circuit.num_measurements

    @property
    def num_moments(self) -> int:
        """Return the number of moments in the circuit representing ``self``."""
        return self.circuit.schedule.max_schedule + 1

    def is_empty(self) -> bool:
        """Check if the plaquette is empty.

        An empty plaquette is a plaquette that contain empty scheduled circuit.

        """
        return bool(self.circuit.get_circuit(include_qubit_coords=False) == stim.Circuit())

    def with_debug_information(self, debug_information: PlaquetteDebugInformation) -> Plaquette:
        """Create a copy of ``self`` with the provided ``debug_information``."""
        return Plaquette(  # pragma: no cover
            self.name,
            self.qubits,
            self.circuit,
            self.mergeable_instructions,
            debug_information,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the plaquette.

        The dictionary is intended to be used as a JSON object.

        """
        return {
            "name": self.name,
            "qubits": self.qubits.to_dict(),
            "circuit": self.circuit.to_dict(),
            "mergeable_instructions": list(self.mergeable_instructions),
            "debug_information": self.debug_information.to_dict(),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Plaquette:
        """Return a plaquette from its dictionary representation.

        Args:
            data: dictionary with the keys ``name``, ``qubits``, ``circuit``,
                ``mergeable_instructions`` and ``debug_information``.

        Returns:
            a new instance of :class:`Plaquette` with the provided
            ``name``, ``qubits``, ``circuit``, ``mergeable_instructions`` and
            ``debug_information``.

        """
        name = data["name"]
        qubits = PlaquetteQubits.from_dict(data["qubits"])
        circuit = ScheduledCircuit.from_dict(data["circuit"])
        mergeable_instructions = frozenset(data["mergeable_instructions"])
        debug_information = PlaquetteDebugInformation.from_dict(data["debug_information"])
        return Plaquette(name, qubits, circuit, mergeable_instructions, debug_information)


@dataclass(frozen=True)
class Plaquettes:
    """Represent a collection of plaquettes that might be applied to a :class:`Template` instance.

    The goal of this class is to abstract away how a "collection of plaquettes" is represented and
    to provide a unique interface in order to retrieve plaquettes when building a quantum circuit
    from a template and plaquettes.

    It also checks that the represented collection is valid, which means that it does not include
    any plaquette associated with index 0 (that is internally and conventionally reserved for the
    empty plaquette).

    """

    collection: FrozenDefaultDict[int, Plaquette]

    def __post_init__(self) -> None:
        if 0 in self.collection:
            raise TQECError(
                "Found a Plaquette with index 0. This index is reserved to express "
                '"no plaquette". Please re-number your plaquettes starting from 1.'
            )

    def __getitem__(self, index: int) -> Plaquette:
        return self.collection[index]

    def with_updated_plaquettes(self, plaquettes_to_update: Mapping[int, Plaquette]) -> Plaquettes:
        """Return a new :class:`.Plaquettes` instance with the updated plaquettes.

        Args:
            plaquettes_to_update: a mapping from plaquette indices to :class:`.Plaquette` instances.
                Each entry will replace an existing (or create a new) entry in a copy of ``self``.

        Returns:
            a new :class:`.Plaquettes` instance with plaquettes from ``self`` and
            ``plaquettes_to_update``. If an index is present in both ``self`` and
            ``plaquettes_to_update``, ``plaquettes_to_update`` take precedence.

        """
        return Plaquettes(self.collection | plaquettes_to_update)

    def map_indices(self, callable: Callable[[int], int]) -> Plaquettes:
        """Return a new :class:`.Plaquettes` instance with updated plaquette indices."""
        return Plaquettes(self.collection.map_keys(callable))

    def __eq__(self, rhs: object) -> bool:
        return isinstance(rhs, Plaquettes) and self.collection == rhs.collection

    def __hash__(self) -> int:
        """Implement hashing for Python's hash().

        The returned value is reliable across runs, interpreters and OSes.

        The returned value is reliable across runs, interpreters and OSes.

        """
        return hash(  # pragma: no cover
            tuple(
                sorted(
                    (index, plaquette.reliable_hash())
                    for index, plaquette in self.collection.items()
                )
            )
        )

    def to_name_dict(self) -> dict[int | Literal["default"], str]:
        """Return a dictionary with each plaquette name as value."""
        d: dict[int | Literal["default"], str] = {k: p.name for k, p in self.collection.items()}
        if self.collection.default_value is not None:
            d["default"] = self.collection.default_value.name
        return d

    def without_plaquettes(self, indices: Collection[int]) -> Plaquettes:
        """Remove the plaquettes at the provided ``indices`` from a copy of ``self``."""
        return Plaquettes(
            FrozenDefaultDict(
                {k: v for k, v in self.collection.items() if k not in indices},
                default_value=self.collection.default_value,
            )
        )

    def items(self) -> Iterable[tuple[int, Plaquette]]:
        """Return an iterable over each :class:`.Plaquette` and its associated index in ``self``."""
        return self.collection.items()  # pragma: no cover

    def to_dict(self, plaquettes_to_indices: dict[Plaquette, int] | None = None) -> dict[str, Any]:
        """Return a dictionary representation of the plaquettes.

        Args:
            plaquettes_to_indices: a dictionary mapping plaquettes to their
                indices. If provided, a plaquette will be represented by its index

        """

        def convert(value: Plaquette) -> Any:
            return plaquettes_to_indices[value] if plaquettes_to_indices else value.to_dict()

        return {
            "plaquettes": [
                {"index": index, "plaquette": convert(plaquette)}
                for index, plaquette in self.collection.items()
            ],
            "default": (
                convert(self.collection.default_value)
                if self.collection.default_value is not None
                else None
            ),
        }

    @staticmethod
    def from_dict(
        data: dict[str, Any], plaquettes: Sequence[Plaquette] | None = None
    ) -> Plaquettes:
        """Return a collection of plaquettes from its dictionary representation.

        Args:
            data: dictionary with the keys ``plaquettes`` and ``default``.
            plaquettes: list of :class:`Plaquette` instances to use to build the
                :class:`Plaquettes` instances. Each plaquette is represented by
                its index in the list of unique plaquettes to save space.

        Returns:
            a new instance of :class:`Plaquettes` with the provided
            ``plaquettes`` and ``default``.

        """

        def convert(item: dict[str, Any]) -> Plaquette:
            return (
                Plaquette.from_dict(item["plaquette"])
                if plaquettes is None
                else plaquettes[item["plaquette"]]
            )

        collection = cast(
            FrozenDefaultDict[int, Plaquette],
            FrozenDefaultDict(
                {int(item["index"]): convert(item) for item in data["plaquettes"]},
                default_value=(
                    (Plaquette.from_dict(data["default"]) if data["default"] else None)
                    if plaquettes is None
                    else (plaquettes[data["default"]] if data["default"] is not None else None)
                ),
            ),
        )
        # If the default value is None, print a WARNING (this should not happen in practice)
        if collection.default_value is None:
            warnings.warn(
                "The default value of the plaquettes collection is None. "
                "This should not happen in practice.",
                TQECWarning,
            )
        return Plaquettes(collection)
