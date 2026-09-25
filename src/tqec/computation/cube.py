"""Defines the :py:class:`~tqec.computation.cube.Cube` class."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import cached_property
from typing import Any

from tqec.computation.correlation import CorrelationSurface
from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Direction3D, Position3D


class ZXCube(Enum):
    """The kind of cubes consisting of only X or Z basis boundaries.

    Attributes:
        x: Looking at the cube along the x-axis, the basis of the walls observed.
        y: Looking at the cube along the y-axis, the basis of the walls observed.
        z: Looking at the cube along the z-axis, the basis of the walls observed.

    """

    ZXZ = Basis.Z, Basis.X, Basis.Z
    XZZ = Basis.X, Basis.Z, Basis.Z
    ZXX = Basis.Z, Basis.X, Basis.X
    XZX = Basis.X, Basis.Z, Basis.X
    XXZ = Basis.X, Basis.X, Basis.Z
    ZZX = Basis.Z, Basis.Z, Basis.X

    @cached_property
    def x(self) -> Basis:
        """Return the basis of the walls along the x-axis."""
        return self.value[0]

    @cached_property
    def y(self) -> Basis:
        """Return the basis of the walls along the y-axis."""
        return self.value[1]

    @cached_property
    def z(self) -> Basis:
        """Return the basis of the walls along the z-axis."""
        return self.value[2]

    def as_tuple(self) -> tuple[Basis, Basis, Basis]:
        """Return a tuple of ``(self.x, self.y, self.z)``.

        Returns:
            A tuple of ``(self.x, self.y, self.z)``.

        """
        return self.value

    def __str__(self) -> str:
        return self.name

    @staticmethod
    def from_str(string: str) -> ZXCube:
        """Create a cube kind from the string representation.

        The string must be a 3-character string consisting of ``'X'`` or ``'Z'``,
        representing the basis of the walls along the x, y, and z axes.
        For example, a cube with left-right walls in the X basis, front-back walls in the Z basis,
        and top-bottom walls in the X basis can be constructed from the string ``'XZX'``.

        Args:
            string: A 3-character string consisting of ``'X'`` or ``'Z'``, representing
                the basis of the walls along the x, y, and z axes.

        Returns:
            The :py:class:`~tqec.computation.cube.ZXCube` instance constructed from
            the string representation.

        """
        try:
            return ZXCube[string.upper()]
        except KeyError:
            raise TQECError(f"Unknown ZX cube kind string representation: {string!r}.")

    @cached_property
    def normal_basis(self) -> Basis:
        """Return the normal basis of the cube.

        Normal basis only appears once in the three bases of the cube. For example,
        the normal basis of the cube ``XZZ`` is ``X`` and the normal basis of the cube
        ``ZXX`` is ``Z``.

        """
        if self.name.count("Z") == 1:
            return Basis.Z
        return Basis.X

    @cached_property
    def normal_direction(self) -> Direction3D:
        """Return the normal direction of the cube.

        Normal direction is the direction along which the normal basis appears.
        For example, the normal direction of the cube ``XZZ`` is ``Direction3D.X``
        and the normal direction of the cube ``XXZ`` is ``Direction3D.Z``.

        """
        return Direction3D(self.name.index(self.normal_basis.name))

    @cached_property
    def is_spatial(self) -> bool:
        """Return whether a cube of this kind is a spatial cube.

        A spatial cube is a cube whose all spatial boundaries are in the same basis.
        There are only two possible spatial cubes: ``XXZ`` and ``ZZX``.

        """
        return self in [ZXCube.XXZ, ZXCube.ZZX]

    def get_basis_along(self, direction: Direction3D) -> Basis:
        """Get the basis of the walls along the given direction axis.

        Args:
            direction: The direction of the axis along which the basis is queried.

        Returns:
            The basis of the walls along the given direction axis.

        """
        return self.value[direction.value]

    def with_basis_along(self, direction: Direction3D, basis: Basis) -> ZXCube:
        """Set the basis of the walls along the given direction axis and return a new instance.

        Args:
            direction: The direction of the axis along which the basis is set.
            basis: The basis to set along the given direction axis.

        Returns:
            The new :py:class:`~tqec.computation.cube.ZXCube` instance with the basis
            set along the given direction axis.

        """
        return ZXCube(tuple(basis if i == direction.value else b for i, b in enumerate(self.value)))

    @staticmethod
    def from_normal_basis_direction(direction: Direction3D, basis: Basis) -> ZXCube:
        """Create a cube kind with the given normal basis and normal direction.

        Args:
            direction: The normal direction of the cube kind to be created.
            basis: The normal basis of the cube kind to be created.

        Returns:
            The :py:class:`~tqec.computation.cube.ZXCube` instance with the given
            normal basis and normal direction.

        """
        kind = [basis.flipped().name] * 3
        kind[direction.value] = basis.name
        return ZXCube["".join(kind)]


class LeafCubeKind(Enum):
    """Cube kinds that can only appear at the leaves of a block graph.

    Attributes:
        PORT: Cube kind representing the open ports in the block graph.
            The open ports correspond to the input/output of the computation represented by the
            block graph. They will have no effect on the functionality of the logical computation
            itself and should be invisible when visualizing the computation model.
        Y_HALF_CUBE: Cube kind representing the Y-basis initialization/measurements.

    """

    PORT = "PORT"
    Y_HALF_CUBE = "Y"
    # CULTIVATION = "T"

    def __str__(self) -> str:
        return self.value

    @staticmethod
    def from_str(string: str) -> LeafCubeKind:
        """Create a leaf cube kind from the string representation.

        Args:
            string: The string representation of the leaf cube kind.

        Returns:
            The :py:class:`~tqec.computation.cube.LeafCubeKind` instance constructed
            from the string representation.

        """
        match string.upper():
            case "PORT" | "P":
                return LeafCubeKind.PORT
            case "Y" | "Y_HALF_CUBE":
                return LeafCubeKind.Y_HALF_CUBE
            # case "T":
            #     return LeafCubeKind.CULTIVATION
            case _:
                raise TQECError(f"Unknown leaf cube kind string representation: {string!r}.")


StaticCubeKind = ZXCube | LeafCubeKind
"""Cube kinds that do not depend on a runtime condition."""


@dataclass(frozen=True)
class ConditionalCubeKind:
    """Cube kind that is resolved at runtime to one of two branch kinds by a classical bit.

    A conditional cube represents an operation whose basis depends on the outcome of
    previous measurements, e.g. the conditional-basis measurement used to auto-correct
    magic state injection. The classical bit selecting the branch is described by the
    :py:attr:`~tqec.computation.cube.Cube.condition` attribute of the cube using the
    kind.

    The two branches must be implementable by the same code patch connected to the
    same single pipe: they must differ, cannot be ports, and two ``ZXCube`` branches
    must have the same wall bases along all but exactly one axis (the axis of the
    pipe connecting the cube to the rest of the computation).

    Note:
        Only conditional measurement cubes with ``ZXCube`` branches (i.e., a
        conditional X-vs-Z measurement basis, connected to a temporal pipe from
        below) can be compiled at the moment. Other conditional kinds expressible
        here (Y-basis branches, spatial-pipe conditionals) can be constructed,
        validated and serialized, but raise ``NotImplementedError`` at compilation.

    Attributes:
        branches: the two branch kinds as
            ``(kind_if_condition_is_0, kind_if_condition_is_1)``.

    """

    branches: tuple[StaticCubeKind, StaticCubeKind]

    def __post_init__(self) -> None:
        object.__setattr__(self, "branches", tuple(self.branches))
        if len(self.branches) != 2:
            raise TQECError(
                f"A conditional cube kind must have exactly two branches, got {self.branches}."
            )
        if self.branches[0] == self.branches[1]:
            raise TQECError("The two branches of a conditional cube kind must differ.")
        if LeafCubeKind.PORT in self.branches:
            raise TQECError("A port cannot be a branch of a conditional cube kind.")
        if all(isinstance(branch, ZXCube) for branch in self.branches):
            if self.pipe_direction is None:
                raise TQECError(
                    "The two ZX branches of a conditional cube kind must have the same "
                    f"wall bases along all but exactly one axis, got {self.branches}."
                )

    @cached_property
    def pipe_direction(self) -> Direction3D | None:
        """Direction of the single pipe a cube of this kind must be connected to.

        For two ``ZXCube`` branches, this is the single axis along which the branch
        wall bases differ: the walls along that axis are opened by the pipe, making
        the two branches compatible with the same pipe. For branches involving a
        ``Y_HALF_CUBE``, this is the time direction, as Y half cubes only connect to
        temporal pipes.

        Returns ``None`` if the branches are not compatible with any single pipe
        (only possible for invalid branch pairs, rejected at construction).

        """
        branch_0, branch_1 = self.branches
        if not (isinstance(branch_0, ZXCube) and isinstance(branch_1, ZXCube)):
            return Direction3D.Z
        differing_directions = [
            direction
            for direction in Direction3D.all_directions()
            if branch_0.get_basis_along(direction) != branch_1.get_basis_along(direction)
        ]
        return differing_directions[0] if len(differing_directions) == 1 else None

    def resolve(self, condition_value: bool | int) -> StaticCubeKind:
        """Return the branch kind selected when the condition evaluates to ``condition_value``."""
        return self.branches[int(bool(condition_value))]

    def __str__(self) -> str:
        return f"{self.branches[0]}_{self.branches[1]}"

    @staticmethod
    def from_str(string: str) -> ConditionalCubeKind:
        """Create a conditional cube kind from the string representation.

        Args:
            string: The string representation of the conditional cube kind: the string
                representations of the two branch kinds joined by an underscore, e.g.
                ``"ZXZ_ZXX"`` or ``"ZXX_Y"``.

        Returns:
            The :py:class:`~tqec.computation.cube.ConditionalCubeKind` instance
            constructed from the string representation.

        """
        parts = string.strip().upper().split("_")
        if len(parts) != 2:
            raise TQECError(
                f"Unknown conditional cube kind string representation: {string!r}. Expected "
                'the two branch kinds joined by an underscore, e.g. "ZXZ_ZXX".'
            )
        branches = [
            ZXCube.from_str(part) if part in ZXCube.__members__ else LeafCubeKind.from_str(part)
            for part in parts
        ]
        return ConditionalCubeKind((branches[0], branches[1]))


CubeKind = ZXCube | LeafCubeKind | ConditionalCubeKind
"""All the possible kinds of cubes."""


def cube_kind_from_string(s: str) -> CubeKind:
    """Create a cube kind from the string representation."""
    s = s.strip().upper()
    if s in ZXCube.__members__:
        return ZXCube.from_str(s)
    if s in LeafCubeKind.__members__ or s in ["PORT", "P", "Y"]:
        return LeafCubeKind.from_str(s)
    if "_" in s:
        return ConditionalCubeKind.from_str(s)
    raise TQECError(f"Unknown cube kind string representation: {s!r}.")


@dataclass(frozen=True, slots=True)
class Cube:
    """A fundamental building block of the logical computation.

    A cube is a high-level abstraction of a block of quantum operations within a
    specific spacetime volume. These operations preserve or manipulate the quantum
    information encoded in the logical qubits.

    For example, a single ``ZXZ`` kind cube can represent a quantum memory experiment for
    a surface code patch in logical Z basis. The default circuit implementation of the
    cube will consist of transversal Z basis resets, syndrome extraction cycles, and finally
    the Z basis transversal measurements. The spatial location of the physical qubits in the
    code patch and the time when the operations are applied are specified by the spacetime
    position of the cube.

    Attributes:
        position: The position of the cube in the spacetime. The spatial coordinates
            determines which code patch the operations are applied to, and the time
            coordinate determines when the operations are applied.
        kind: The kind of the cube. It determines the basic logical operations represented
            by the cube.
        label: The label of the cube. It's mainly used for annotating the input/output
            ports of the block graph. If the cube is a port, the label must be non-empty
            and unique within the block graph. The label can be any string, but duplicate
            labels are not allowed. Default is an empty string.

    """

    position: Position3D
    kind: CubeKind
    label: str = ""
    condition: CorrelationSurface | None = None

    def __post_init__(self) -> None:
        if self.is_port and not self.label:
            raise TQECError("A port cube must have a non-empty port label.")
        if self.condition is None and self.is_conditional:
            raise TQECError("A conditional cube must have a specified condition.")
        if self.condition is not None:
            if not self.is_conditional:
                raise TQECError("Only a conditional cube can have a condition.")
            if any(cond_pos.z >= self.position.z for cond_pos in self.condition.positions):
                raise TQECError("Condition must be in the past of the cube being conditioned.")

    def __str__(self) -> str:
        return f"{self.kind}{self.position}"

    @property
    def is_conditional(self) -> bool:
        """Return whether the cube is a conditional cube."""
        return isinstance(self.kind, ConditionalCubeKind)

    def resolve(self, condition_value: bool | int) -> Cube:
        """Return a static cube with the conditional kind resolved to one of its branches.

        Args:
            condition_value: the runtime value of the condition. The returned cube has
                the kind of the corresponding branch.

        Returns:
            ``self`` if the cube is not conditional, else a new cube with the same
            position and label, the resolved static kind and no condition.

        """
        if not isinstance(self.kind, ConditionalCubeKind):
            return self
        return Cube(self.position, self.kind.resolve(condition_value), self.label)

    @property
    def is_zx_cube(self) -> bool:
        """Verify whether the cube is of kind ``ZXCube``."""
        return isinstance(self.kind, ZXCube)

    @property
    def is_port(self) -> bool:
        """Verify whether the cube is of kind ``PORT``."""
        return self.kind is LeafCubeKind.PORT

    @property
    def is_y_cube(self) -> bool:
        """Verify whether the cube is of kind ``Y_HALF_CUBE``."""
        return self.kind is LeafCubeKind.Y_HALF_CUBE

    @property
    def is_spatial(self) -> bool:
        """Return whether the cube is a spatial cube.

        A spatial cube is a cube whose all spatial boundaries are in the same basis.
        There are only two possible spatial cubes: ``XXZ`` and ``ZZX``.

        """
        return isinstance(self.kind, ZXCube) and self.kind.is_spatial

    def to_dict(self) -> dict[str, Any]:
        """Return the dictionary representation of the cube."""
        return {
            "position": self.position.as_tuple(),
            "kind": str(self.kind),
            "label": self.label,
            "condition": self.condition.to_dict() if self.condition is not None else None,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Cube:
        """Create a cube from the dictionary representation.

        Args:
            data: The dictionary representation of the cube.

        Returns:
            The :py:class:`~tqec.computation.cube.Cube` instance created from the
            dictionary representation.

        """
        return Cube(
            position=Position3D(*data["position"]),
            kind=cube_kind_from_string(data["kind"]),
            label=data["label"],
            condition=None
            if (condition := data.get("condition", None)) is None
            else CorrelationSurface.from_dict(condition),
        )
