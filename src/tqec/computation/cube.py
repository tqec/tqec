"""Defines the :py:class:`~tqec.computation.cube.Cube` class."""

from __future__ import annotations

from dataclasses import astuple, dataclass
from typing import Any

from tqec.utils.enums import Basis
from tqec.utils.exceptions import TQECError
from tqec.utils.position import Direction3D, Position3D


@dataclass(frozen=True)
class ZXCube:
    """The kind of cubes consisting of only X or Z basis boundaries.

    Attributes:
        x: Looking at the cube along the x-axis, the basis of the walls observed.
        y: Looking at the cube along the y-axis, the basis of the walls observed.
        z: Looking at the cube along the z-axis, the basis of the walls observed.

    """

    x: Basis
    y: Basis
    z: Basis

    def __post_init__(self) -> None:
        if self.x == self.y == self.z:
            raise TQECError("The cube with the same basis along all axes is not allowed.")

    def as_tuple(self) -> tuple[Basis, Basis, Basis]:
        """Return a tuple of ``(self.x, self.y, self.z)``.

        Returns:
            A tuple of ``(self.x, self.y, self.z)``.

        """
        return astuple(self)

    def __str__(self) -> str:
        return f"{self.x}{self.y}{self.z}"

    @staticmethod
    def all_kinds() -> list[ZXCube]:
        """Return all the allowed ``ZXCube`` instances.

        Returns:
            The list of all the allowed ``ZXCube`` instances.

        """
        return [ZXCube.from_str(s) for s in ["ZXZ", "XZZ", "ZXX", "XZX", "XXZ", "ZZX"]]

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
        return ZXCube(*map(Basis, string.upper()))

    @property
    def normal_basis(self) -> Basis:
        """Return the normal basis of the cube.

        Normal basis only appears once in the three bases of the cube. For example,
        the normal basis of the cube ``XZZ`` is ``X`` and the normal basis of the cube
        ``ZXX`` is ``Z``.

        """
        if sum(basis == Basis.Z for basis in astuple(self)) == 1:
            return Basis.Z
        return Basis.X

    @property
    def normal_direction(self) -> Direction3D:
        """Return the normal direction of the cube.

        Normal direction is the direction along which the normal basis appears.
        For example, the normal direction of the cube ``XZZ`` is ``Direction3D.X``
        and the normal direction of the cube ``XXZ`` is ``Direction3D.Z``.

        """
        return Direction3D(astuple(self).index(self.normal_basis))

    @property
    def is_spatial(self) -> bool:
        """Return whether a cube of this kind is a spatial cube.

        A spatial cube is a cube whose all spatial boundaries are in the same basis.
        There are only two possible spatial cubes: ``XXZ`` and ``ZZX``.

        """
        return self.x == self.y

    def get_basis_along(self, direction: Direction3D) -> Basis:
        """Get the basis of the walls along the given direction axis.

        Args:
            direction: The direction of the axis along which the basis is queried.

        Returns:
            The basis of the walls along the given direction axis.

        """
        return self.as_tuple()[direction.value]

    def with_basis_along(self, direction: Direction3D, basis: Basis) -> ZXCube:
        """Set the basis of the walls along the given direction axis and return a new instance.

        Args:
            direction: The direction of the axis along which the basis is set.
            basis: The basis to set along the given direction axis.

        Returns:
            The new :py:class:`~tqec.computation.cube.ZXCube` instance with the basis
            set along the given direction axis.

        """
        return ZXCube(
            *[basis if i == direction.value else b for i, b in enumerate(self.as_tuple())]
        )


class Port:
    """Cube kind representing the open ports in the block graph.

    The open ports correspond to the input/output of the computation represented by the block graph.
    They will have no effect on the functionality of the logical computation itself and should be
    invisible when visualizing the computation model.

    """

    def __str__(self) -> str:
        return "PORT"

    def __hash__(self) -> int:
        return hash(Port)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Port)


class YHalfCube:
    """Cube kind representing the Y-basis initialization/measurements."""

    def __str__(self) -> str:
        return "Y"

    def __hash__(self) -> int:
        return hash(YHalfCube)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, YHalfCube)


CubeKind = ZXCube | Port | YHalfCube
"""All the possible kinds of cubes."""


def cube_kind_from_string(s: str) -> CubeKind:
    """Create a cube kind from the string representation."""
    match s.upper():
        case "PORT" | "P":
            return Port()
        case "Y":
            return YHalfCube()
        case _:
            return ZXCube.from_str(s)


@dataclass(frozen=True)
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

    def __post_init__(self) -> None:
        if self.is_port and not self.label:
            raise TQECError("A port cube must have a non-empty port label.")

    def __str__(self) -> str:
        return f"{self.kind}{self.position}"

    @property
    def is_zx_cube(self) -> bool:
        """Verify whether the cube is of kind :py:class:`~tqec.computation.cube.ZXCube`."""
        return isinstance(self.kind, ZXCube)

    @property
    def is_port(self) -> bool:
        """Verify whether the cube is of kind :py:class:`~tqec.computation.cube.Port`."""
        return isinstance(self.kind, Port)

    @property
    def is_y_cube(self) -> bool:
        """Verify whether the cube is of kind :py:class:`~tqec.computation.cube.YHalfCube`."""
        return isinstance(self.kind, YHalfCube)

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
        )
