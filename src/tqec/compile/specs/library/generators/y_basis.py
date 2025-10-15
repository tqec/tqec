"""Build injection blocks for Y-basis initialization and measurement.

The circuit construction refers to the code from: https://github.com/Strilanc/inplace-y-basis-2023
with modification to support different boundary conditions and conventions.
"""

import functools
from collections.abc import Callable, Iterable, Set
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, cast

import gen

from tqec.compile.blocks.block import CircuitWithInterface, InjectedBlock
from tqec.compile.blocks.enums import Alignment
from tqec.compile.specs.base import YHalfCubeSpec
from tqec.utils.enums import Basis
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D

DIRS: list[complex] = [(0.5 + 0.5j) * 1j**d for d in range(4)]
DR, DL, UL, UR = DIRS

class DiagonalType(Enum):
    """Type of diagonal in the surface code patch.

    MAIN: Top-left to bottom-right diagonal where real + imag = constant
    ANTI: Bottom-left to top-right diagonal where real - imag = constant
    """
    MAIN = "main"
    ANTI = "anti"


@dataclass(frozen=True)
class TwistLine:
    """Represents a domain wall in the Y-basis transition.
    
    Attributes:
        diagonal: Whether this is a main diagonal or anti-diagonal
        position: Which diagonal line (as an offset from origin)
        orientation: The stabilizer basis orientation along the twist (X or Z)
    """
    diagonal: DiagonalType
    position: int
    orientation: Basis

    def contains(self, m: complex) -> bool:
        """Check if measurement qubit m lies on this twist line.

        Args:
            m: Complex number representing qubit position

        Returns:
            True if m is on the twist line
        """
        if self.diagonal == DiagonalType.MAIN:
            return int(m.real + m.imag) == self.position
        else:
            return int(m.real - m.imag) == self.position

    def is_before(self, m: complex) -> bool:
        """Check if measurement qubit m is before (above/left of) the twist line."""
        if self.diagonal == DiagonalType.MAIN:
            return m.real + m.imag < self.position
        else:
            return m.real - m.imag < self.position

    def is_after(self, m: complex) -> bool:
        """Check if measurement qubit m is after (below/right of) the twist line."""
        if self.diagonal == DiagonalType.MAIN:
            return m.real + m.imag > self.position
        else:
            return m.real - m.imag > self.position


@dataclass(frozen=True)
class BoundaryRegion:
    """Represents boundary regions in the surface code patch.

    Attributes:
        top_row: Set of qubits on the top boundary (imag = -0.5)
        bottom_row: Set of qubits on the bottom boundary
        left_col: Set of qubits on the left boundary (real = -0.5)
        right_col: Set of qubits on the right boundary
    """
    top_row: frozenset[complex]
    bottom_row: frozenset[complex]
    left_col: frozenset[complex]
    right_col: frozenset[complex]

    def is_boundary(self, m: complex) -> bool:
        """Check if qubit m is on any boundary."""
        return m in self.top_row or m in self.bottom_row or m in self.left_col or m in self.right_col


@dataclass(frozen=True)
class TransitionGeometry:
    """Geometric description of a Y-basis transition circuit.

    This class encapsulates all the geometric information needed to understand
    and generate a Y-basis transition circuit, making the implicit geometric
    constraints explicit.

    Attributes:
        distance: Code distance
        top_boundary_basis: Basis of the top boundary 
        convention: Boundary convention 
        twist_line: The twist line in the transition
        boundary: Boundary regions of the patch
        top_left_tile_basis: Basis of the top-left tile in checkerboard
    """
    distance: int
    top_boundary_basis: Basis
    convention: Literal["fixed_boundary", "fixed_bulk"]
    twist_line: TwistLine
    boundary: BoundaryRegion
    top_left_tile_basis: Basis

    @classmethod
    def from_convention(
        cls,
        distance: int,
        top_boundary_basis: Basis,
        convention: Literal["fixed_boundary", "fixed_bulk"],
    ) -> "TransitionGeometry":
        """Construct transition geometry from convention parameters.

        Args:
            distance: Code distance
            top_boundary_basis: Basis of top boundary (X or Z)
            convention: "fixed_boundary" or "fixed_bulk"

        Returns:
            Geometric description of the transition
        """
        # Determine top-left tile basis (same logic as _get_top_left_tile_basis)
        if convention == "fixed_boundary" and top_boundary_basis == Basis.X:
            top_left_tile_basis = Basis.X
        else:
            top_left_tile_basis = Basis.Z

        # Determine twist line placement
        # Main diagonal (real + imag = const)
        # The position is always at distance - 1
        twist_line = TwistLine(
            diagonal=DiagonalType.MAIN,
            position=distance - 1,
            orientation=Basis.X if top_left_tile_basis == Basis.Z else Basis.Z,
        )

        # Build boundary regions
        # These are measurement qubit positions (at half-integer coordinates)
        top_row = frozenset(complex(x + 0.5, -0.5) for x in range(-1, distance))
        bottom_row = frozenset(complex(x + 0.5, distance - 0.5) for x in range(-1, distance))
        left_col = frozenset(complex(-0.5, y + 0.5) for y in range(-1, distance))
        right_col = frozenset(complex(distance - 0.5, y + 0.5) for y in range(-1, distance))

        boundary = BoundaryRegion(top_row, bottom_row, left_col, right_col)

        return cls(
            distance=distance,
            top_boundary_basis=top_boundary_basis,
            convention=convention,
            twist_line=twist_line,
            boundary=boundary,
            top_left_tile_basis=top_left_tile_basis,
        )

    def get_new_boundary_for_basis(self, tile_basis: Basis | str) -> frozenset[complex]:
        """Get the new boundary qubits for a given tile basis after transition.

        During Y-transition, boundaries change. This computes which boundary
        becomes active for X-type or Z-type stabilizers after transition.

        Args:
            tile_basis: Basis as Basis enum or string "X"/"Z"
        """
        # Normalize to Basis enum for consistent comparison
        basis_enum = tile_basis if isinstance(tile_basis, Basis) else Basis(tile_basis)

        if self.top_boundary_basis == Basis.X:
            # X-top transitions to having Z on top and X on left
            return self.boundary.left_col if basis_enum == Basis.X else self.boundary.top_row
        else:  # Z-top
            # Z-top transitions to having X on top and Z on left
            return self.boundary.top_row if basis_enum == Basis.X else self.boundary.left_col

    def get_old_boundary_for_basis(self, tile_basis: Basis | str) -> frozenset[complex]:
        """Get the old boundary qubits for a given tile basis before transition.

        Args:
            tile_basis: Basis as Basis enum or string "X"/"Z"
        """
        # Normalize to Basis enum for consistent comparison
        basis_enum = tile_basis if isinstance(tile_basis, Basis) else Basis(tile_basis)

        if self.top_boundary_basis == Basis.X:
            # Before transition: X on top, Z on left
            return self.boundary.top_row if basis_enum == Basis.X else self.boundary.left_col
        else:  # Z-top
            # Before transition: Z on top, X on left
            return self.boundary.left_col if basis_enum == Basis.X else self.boundary.top_row
# Interaction orderings that are consistent with the plaquette
# orderings used across TQEC
ORDER_H = [UL, UR, DL, DR]
ORDER_V = [UL, DL, UR, DR]


def _surface_code_patch(
    possible_data_qubits: Iterable[complex],
    basis: Callable[[complex], Basis],
    is_boundary_x: Callable[[complex], bool],
    is_boundary_z: Callable[[complex], bool],
    order_func: Callable[[complex], Iterable[complex | None]],
) -> gen.Patch:
    """Make a surface code patch."""
    possible_data_qubits = set(possible_data_qubits)
    possible_measure_qubits = {q + d for q in possible_data_qubits for d in DIRS}
    measure_qubits = {
        m
        for m in possible_measure_qubits
        if sum(m + d in possible_data_qubits for d in DIRS) > 1
        if is_boundary_x(m) <= (basis(m) == Basis.X)
        if is_boundary_z(m) <= (basis(m) == Basis.Z)
    }
    data_qubits = {
        q for q in possible_data_qubits if sum(q + d in measure_qubits for d in DIRS) > 1
    }

    tiles = [
        gen.Tile(
            bases=str(basis(m)),
            data_qubits=[
                m + d if d is not None and m + d in data_qubits else None for d in order_func(m)
            ],
            measure_qubit=m,
        )
        for m in measure_qubits
    ]
    return gen.Patch(tiles)


def _checkerboard_basis(q: complex, top_left_tile_basis: Basis) -> Basis:
    """Classifies a coordinate as X type or Z type according to a checkerboard."""
    if int(q.real + q.imag) & 1 == 0:
        return top_left_tile_basis.flipped()
    return top_left_tile_basis


def _rectangular_surface_code_patch(
    width: int,
    height: int,
    top_left_tile_basis: Basis,
    top_basis: Basis,
    bot_basis: Basis,
    left_basis: Basis,
    right_basis: Basis,
    order_func: Callable[[complex], Iterable[complex | None]],
) -> gen.Patch:
    """Make a rectangular surface code patch."""

    def is_boundary(m: complex, *, b: Basis) -> bool:
        if top_basis == b and m.imag == -0.5:
            return True
        if left_basis == b and m.real == -0.5:
            return True
        if bot_basis == b and m.imag == height - 0.5:
            return True
        if right_basis == b and m.real == width - 0.5:
            return True
        return False

    return _surface_code_patch(
        possible_data_qubits=[x + 1j * y for x in range(width) for y in range(height)],
        basis=lambda q: _checkerboard_basis(q, top_left_tile_basis),
        is_boundary_x=functools.partial(is_boundary, b=Basis.X),
        is_boundary_z=functools.partial(is_boundary, b=Basis.Z),
        order_func=order_func,
    )


def _get_top_left_tile_basis(
    top_boundary_basis: Basis,
    convention: Literal["fixed_boundary", "fixed_bulk"],
) -> Basis:
    """Get the basis of the top-left tile given the top boundary basis and convention."""
    if convention == "fixed_boundary" and top_boundary_basis == Basis.X:
        return Basis.X
    return Basis.Z


def _make_qubit_patch(
    distance: int,
    top_boundary_basis: Basis,
    convention: Literal["fixed_boundary", "fixed_bulk"],
) -> gen.Patch:
    """Make a surface code patch that has the specific boundary orientation and convention."""
    top_left_tile_basis = _get_top_left_tile_basis(top_boundary_basis, convention)

    def order_func(m: complex) -> list[complex]:
        if (_checkerboard_basis(m, top_left_tile_basis) == Basis.X) ^ (
            top_boundary_basis == Basis.Z
        ):
            return ORDER_H
        return ORDER_V

    return _rectangular_surface_code_patch(
        width=distance,
        height=distance,
        top_left_tile_basis=top_left_tile_basis,
        top_basis=top_boundary_basis,
        right_basis=top_boundary_basis.flipped(),
        bot_basis=top_boundary_basis,
        left_basis=top_boundary_basis.flipped(),
        order_func=order_func,
    )


def _make_yboundary_degenerate_patch(
    distance: int,
    top_boundary_basis_before_transition: Basis,
    convention: Literal["fixed_boundary", "fixed_bulk"],
) -> gen.Patch:
    """Make the degenerate surface code patch at the end of a Y-basis measurement."""
    top_left_tile_basis_before_transition = _get_top_left_tile_basis(
        top_boundary_basis_before_transition, convention
    )

    def order_func(m: complex) -> list[complex]:
        if (_checkerboard_basis(m, top_left_tile_basis_before_transition) == Basis.X) ^ (
            top_boundary_basis_before_transition == Basis.Z
        ):
            return ORDER_H
        return ORDER_V

    if top_boundary_basis_before_transition == Basis.X:
        top_basis = right_basis = Basis.Z
        left_basis = bot_basis = Basis.X
    else:
        top_basis = right_basis = Basis.X
        left_basis = bot_basis = Basis.Z

    return _rectangular_surface_code_patch(
        width=distance,
        height=distance,
        top_left_tile_basis=top_left_tile_basis_before_transition,
        top_basis=top_basis,
        right_basis=right_basis,
        bot_basis=bot_basis,
        left_basis=left_basis,
        order_func=order_func,
    )


def _build_surface_code_round_circuit(
    patch: gen.Patch,
    *,
    init_data_basis: str | dict[complex, str] | None = None,
    measure_data_basis: str | dict[complex, str] | None = None,
    save_layer: Any,
    out: gen.ChunkBuilder,
) -> None:
    """Build a standard surface code round circuit into an existing ChunkBuilder."""
    measure_xs = gen.Patch([tile for tile in patch.tiles if tile.basis == "X"])
    measure_zs = gen.Patch([tile for tile in patch.tiles if tile.basis == "Z"])
    if init_data_basis is None:
        init_data_basis = {}
    elif isinstance(init_data_basis, str):
        init_data_basis = {q: init_data_basis for q in patch.data_set}
    if measure_data_basis is None:
        measure_data_basis = {}
    elif isinstance(measure_data_basis, str):
        measure_data_basis = {q: measure_data_basis for q in patch.data_set}

    out.append("RX", measure_xs.measure_set)
    for basis in "XYZ":
        qs = [q for q in init_data_basis if init_data_basis[q] == basis]
        if qs:
            out.append(f"R{basis}", qs)
    out.append("R", measure_zs.measure_set)
    out.append("TICK")

    (num_layers,) = {len(tile.data_qubits) for tile in patch.tiles}
    for k in range(num_layers):
        out.append(
            "CX",
            [
                (tile.measure_qubit, tile.data_qubits[k])[:: -1 if tile.basis == "Z" else +1]
                for tile in patch.tiles
                if tile.data_qubits[k] is not None
            ],
        )
        out.append("TICK")

    def measure_key_func(pos: complex) -> tuple[complex, Any]:
        return (pos, save_layer)

    out.append("MX", measure_xs.measure_set, measure_key_func=measure_key_func)
    for basis in "XYZ":
        qs = [q for q in measure_data_basis if measure_data_basis[q] == basis]
        if qs:
            out.append(f"M{basis}", qs, measure_key_func=measure_key_func)
    out.append("M", measure_zs.measure_set, measure_key_func=measure_key_func)


def _standard_surface_code_chunk(
    patch: gen.Patch,
    init_data_basis: str | dict[complex, str] | None = None,
    measure_data_basis: str | dict[complex, str] | None = None,
    obs: gen.PauliMap | None = None,
) -> gen.Chunk:
    """Make a standard surface code round circuit chunk."""
    if init_data_basis is None:
        init_data_basis = {}
    elif isinstance(init_data_basis, str):
        init_data_basis = {q: init_data_basis for q in patch.data_set}
    if measure_data_basis is None:
        measure_data_basis = {}
    elif isinstance(measure_data_basis, str):
        measure_data_basis = {q: measure_data_basis for q in patch.data_set}

    builder = gen.ChunkBuilder(allowed_qubits=patch.used_set)
    save_layer = "solo"
    _build_surface_code_round_circuit(
        patch=patch,
        init_data_basis=init_data_basis,
        measure_data_basis=measure_data_basis,
        save_layer=save_layer,
        out=builder,
    )

    if not init_data_basis:
        for tile in patch.tiles:
            builder.add_flow(
                center=tile.measure_qubit,
                start=tile.to_pauli_map(),
                ms=[(tile.measure_qubit, save_layer)],
            )
    if not measure_data_basis:
        for tile in patch.tiles:
            builder.add_flow(
                center=tile.measure_qubit,
                end=tile.to_pauli_map(),
                ms=[(tile.measure_qubit, save_layer)],
            )
    for tile in patch.tiles:
        if all(
            q is None or init_data_basis.get(q) == b for q, b in zip(tile.data_qubits, tile.bases)
        ):
            builder.add_flow(
                center=tile.measure_qubit,
                ms=[(tile.measure_qubit, save_layer)],
            )
    for tile in patch.tiles:
        if all(
            q is None or measure_data_basis.get(q) == b
            for q, b in zip(tile.data_qubits, tile.bases)
        ):
            builder.add_flow(
                center=tile.measure_qubit,
                ms=[(q, save_layer) for q in tile.used_set],
            )
    if obs is not None:
        start_obs = dict(obs.qubits)
        end_obs = dict(obs.qubits)
        for q in init_data_basis:
            if q in start_obs:
                if start_obs.pop(q) != init_data_basis[q]:
                    raise ValueError("wrong init basis for obs")
        ms = []
        for q in measure_data_basis:
            if q in end_obs:
                if end_obs.pop(q) != measure_data_basis[q]:
                    raise ValueError("wrong measure basis for obs")
                ms.append((q, save_layer))

        builder.add_flow(
            center=0,
            start=gen.PauliMap(start_obs),  # type: ignore[arg-type]
            end=gen.PauliMap(end_obs),  # type: ignore[arg-type]
            obs_key=0,
            ms=ms,
        )

    return builder.finish_chunk()


def _split_ul_md_dr(
    ps: Set[complex], distance: int
) -> tuple[set[complex], set[complex], set[complex]]:
    """Split the qubits into sets by their positions: upper-left, middle, down-right."""
    ul: set[complex] = set()
    md: set[complex] = set()
    dr: set[complex] = set()
    for m in ps:
        dst: set[complex]
        if m.real + m.imag < distance - 2:
            dst = ul
        elif m.real + m.imag >= distance:
            dst = dr
        else:
            dst = md
        dst.add(m)
    return ul, md, dr


def _make_y_transition_round(
    distance: int,
    top_boundary_basis_before_transition: Basis,
    convention: Literal["fixed_boundary", "fixed_bulk"],
    include_observables: Iterable[int] = (0,),
) -> gen.Chunk:
    """Make the circuit chunk for transition from qubit patch to degenerate patch."""
    # Create explicit geometry object to make constraints clear
    geometry = TransitionGeometry.from_convention(
        distance, top_boundary_basis_before_transition, convention
    )

    start = _make_qubit_patch(distance, top_boundary_basis_before_transition, convention)
    end = _make_yboundary_degenerate_patch(
        distance, top_boundary_basis_before_transition, convention
    )
    used = start.used_set | end.used_set

    top_left_tile_basis = geometry.top_left_tile_basis
    top_basis = str(top_boundary_basis_before_transition)

    def _m_basis(m: complex) -> Basis | None:
        if m.real % 1 == 0:
            return None
        return _checkerboard_basis(m, top_left_tile_basis)

    xs = {q for q in used if _m_basis(q) == Basis.X}
    zs = {q for q in used if _m_basis(q) == Basis.Z}
    top_row = {q for q in used if q.imag == -0.5}
    left_col = {q for q in used if q.real == -0.5}

    def toward(qs: Set[complex], delta: complex, sign: int) -> set[tuple[complex, complex]]:
        result: set[tuple[complex, complex]] = set()
        for q in qs:
            if q + delta in used:
                result.add(cast(tuple[complex, complex], (q, q + delta)[::sign]))
        return result

    xs_ul, xs_md, xs_dr = _split_ul_md_dr(xs, distance)
    zs_ul, zs_md, zs_dr = _split_ul_md_dr(zs, distance)

    if top_basis == "X":
        normal_x_order, normal_z_order = ORDER_H, ORDER_V
        old_x_boundary, new_x_boundary = top_row, left_col
        old_z_boundary, new_z_boundary = left_col, top_row
    else:
        normal_x_order, normal_z_order = ORDER_V, ORDER_H
        old_x_boundary, new_x_boundary = left_col, top_row
        old_z_boundary, new_z_boundary = top_row, left_col

    builder = gen.ChunkBuilder(used)
    builder.append("RX", (xs - new_x_boundary) | old_x_boundary)
    builder.append("R", (zs - new_z_boundary) | old_z_boundary)
    builder.append("TICK")
    builder.append("CX", toward(xs - new_x_boundary, normal_x_order[-1], +1))
    builder.append("CX", toward(zs - new_z_boundary, normal_z_order[-1], -1))
    builder.append("TICK")
    builder.append("CX", toward(xs - new_x_boundary, normal_x_order[-2], +1))
    builder.append("CX", toward(zs - new_z_boundary, normal_z_order[-2], -1))
    builder.append("TICK")
    if top_left_tile_basis == Basis.Z:
        builder.append("CX", toward(xs_ul, normal_x_order[-3], -1))
        builder.append("CX", toward(zs_ul | zs_md, normal_z_order[-3], +1))
        builder.append("ZCY", toward(xs_md, normal_x_order[-3], +1))
    else:
        builder.append("CX", toward(xs_ul | xs_md, normal_x_order[-3], -1))
        builder.append("CX", toward(zs_ul, normal_z_order[-3], +1))
        builder.append("XCY", toward(zs_md, normal_z_order[-3], +1))
    builder.append("CX", toward(xs_dr, normal_x_order[-3], +1))
    builder.append("CX", toward(zs_dr, normal_z_order[-3], -1))
    builder.append("TICK")
    builder.append("CX", toward(xs_ul, normal_x_order[-1], -1))
    builder.append("CX", toward(zs_ul, normal_x_order[-1], +1))
    builder.append("CX", toward(xs_dr, normal_x_order[-4], +1))
    builder.append("CX", toward(zs_dr, normal_z_order[-4], -1))
    builder.append("TICK")
    if top_left_tile_basis == Basis.Z:
        builder.append("ZCY", toward(zs_md - old_z_boundary, normal_z_order[-1], -1))
    else:
        builder.append("XCY", toward(xs_md - old_x_boundary, normal_x_order[-1], -1))
    builder.append("TICK")
    builder.append("H", [q for q in used if q.real + q.imag < distance - 1])
    if top_left_tile_basis == Basis.Z:
        builder.append(
            "S", [q for q in used if q.real + q.imag == distance - 1 and q.real % 1 == 0.5]
        )
    else:
        builder.append(
            "SQRT_X", [q for q in used if q.real + q.imag == distance - 1 and q.real % 1 == 0.5]
        )
    builder.append("TICK")

    def measure_key_func(pos: complex) -> tuple[complex, Any]:
        return (pos, "solo")

    builder.append("MX", (xs - old_x_boundary) | new_x_boundary, measure_key_func=measure_key_func)
    if top_basis == "X" and convention == "fixed_bulk":
        my_target = complex(0, distance - 1)
    else:
        my_target = complex(distance - 1, 0)
    builder.append("MY", {my_target}, measure_key_func=measure_key_func)
    builder.append("MZ", (zs - old_z_boundary) | new_z_boundary, measure_key_func=measure_key_func)

    # Annotate input stabilizers that get measured.
    # For each stabilizer entering the Y-transition (e.g., X0*X1*X2*X3 for an X-plaquette),
    # we specify which measurements must be XOR'd to detect stabilizer violations.
    # The "mids" (measurement IDs) are the qubit positions whose measurements contribute
    # to the detector.
    for tile in start.tiles:
        m = tile.measure_qubit
        assert m is not None
        assert tile.basis in ("X", "Z")
        mids = _get_mids_for_in_flow(m, tile.basis, geometry)
        builder.add_flow(
            start=tile.to_pauli_map(),  # Input stabilizer (e.g., X₀X₁X₂X₃)
            center=m,
            ms=[(k, "solo") for k in mids],  # Measurements to XOR for detector
        )

    # Annotate output stabilizers that get prepared.
    # For each stabilizer exiting the Y-transition to continue into subsequent computation,
    # we specify which measurements initialize/prepare that stabilizer.
    for tile in end.tiles:
        m = tile.measure_qubit
        assert m is not None
        mids = _get_mids_for_out_flow(m, geometry)

        builder.add_flow(
            end=tile.to_pauli_map(),  # Output stabilizer
            center=m,
            ms=[(k, "solo") for k in mids],  # Measurements that prepare this stabilizer
        )

    # Annotate how observable flows through the system.
    # Contrast to the observable in the paper, the annotated observable is composed
    # of the two X/Z midline operators.
    observables = sorted(include_observables)
    if observables:
        half_d = distance // 2
        center_dq = complex(half_d, half_d)
        vertical_basis = top_boundary_basis_before_transition
        horizontal_basis = top_boundary_basis_before_transition.flipped()

        mset_ur = xs if top_basis == "Z" else zs
        mset_dl = xs if top_basis == "X" else zs
        start = gen.PauliMap(
            {
                center_dq: "Y",
                **{
                    complex(q, half_d): str(horizontal_basis)
                    for q in range(distance)
                    if q != half_d
                },
                **{complex(half_d, q): str(vertical_basis) for q in range(distance) if q != half_d},
            }
        )
        ms = [
            (m, "solo")
            for m in [
                my_target,
                *[q for q in mset_ur | top_row if q.real > half_d and q.imag < half_d],
                *[q for q in mset_dl | left_col if q.real < half_d and q.imag > half_d],
            ]
        ]
        for idx in observables:
            builder.add_flow(
                center=center_dq,
                start=start,
                ms=ms,
                obs_key=idx,
            )

    return builder.finish_chunk()


def _get_mids_for_in_flow(
    m: complex,
    tile_basis: str,
    geometry: TransitionGeometry,
) -> list[complex]:
    """Get measurement qubit positions whose measurements must be XOR'd for input stabilizer flow. The measurement positions depend on the qubit's relationship to the twist line and boundaries.

    Args:
        m: Position of the tile's measurement qubit (ancilla).
        tile_basis: Basis of the stabilizer ("X" or "Z").
        geometry: Geometric description of the transition.

    Returns:
        List of qubit positions (mids = "measurement IDs") whose measurement outcomes
        must be XOR'd together to verify the input stabilizer. The stabilizer enters
        the Y-transition circuit and these measurements detect if it was violated.
    """
    # On the twist line: need two measurements
    if geometry.twist_line.contains(m):
        # For fixed_bulk with X-top, use different offset
        if geometry.convention == "fixed_bulk" and geometry.top_boundary_basis == Basis.X:
            return [m, m - 1j]
        else:
            return [m, m - 1]

    # On boundary: single measurement suffices
    elif geometry.boundary.is_boundary(m):
        return [m]

    # Before twist line (upper-left region): measurement with offset
    elif geometry.twist_line.is_before(m):
        if tile_basis == "X":
            # X stabilizers: offset depends on top basis
            return [m - 1] if geometry.top_boundary_basis == Basis.Z else [m - 1j]
        else:  # Z stabilizers
            return [m - 1j] if geometry.top_boundary_basis == Basis.Z else [m - 1]

    # After twist line (lower-right region): single measurement
    elif geometry.twist_line.is_after(m):
        return [m]

    else:
        raise NotImplementedError(f"{m=!r}, geometry={geometry}")


def _get_mids_for_out_flow(
    m: complex,
    geometry: TransitionGeometry,
) -> list[complex]:
    """Get measurement qubit positions whose measurements must be XOR'd for output stabilizer flow.

    Args:
        m: Position of the tile's measurement qubit (ancilla).
        geometry: Geometric description of the transition.

    Returns:
        List of qubit positions (mids = "measurement IDs") whose measurement outcomes
        must be XOR'd together to prepare the output stabilizer. The stabilizer exits
        the Y-transition circuit to continue into subsequent computation.
    """
    is_fixed_bulk_xtop = (geometry.convention == "fixed_bulk" and
                         geometry.top_boundary_basis == Basis.X)

    # Special corner positions that need extra measurements
    corner_with_extra = (
        complex(0.5, geometry.distance - 1.5) if is_fixed_bulk_xtop
        else complex(geometry.distance - 1.5, 0.5)
    )

    opposite_corner = (
        complex(-0.5, 0.5) if is_fixed_bulk_xtop
        else complex(0.5, -0.5)
    )

    # Corner with four measurements (complex boundary interaction)
    if m == corner_with_extra:
        offset = DL if is_fixed_bulk_xtop else UR
        return [m, m - 1, m - 1j, m + offset]

    # Opposite corner (single measurement)
    elif m == opposite_corner:
        return [m]

    # Top row boundary
    elif m.imag == -0.5:
        return [m, m - 1]

    # Left column boundary
    elif m.real == -0.5:
        return [m, m - 1j]

    # On the twist line after transition
    elif geometry.twist_line.contains(m):
        return [m, m - 1, m - 1j]

    # All other positions (single measurement)
    else:
        return [m]


def _make_y_basis_measurement_chunks(
    distance: int,
    top_boundary_basis_before_measure: Basis,
    convention: Literal["fixed_boundary", "fixed_bulk"],
    padding_rounds: int,
    transform: Callable[[complex], complex] = lambda x: x,
    include_observables: Iterable[int] = (0,),
    close_obs_flows: bool = False,
    include_open_flows: bool = True,
) -> list[gen.Chunk | gen.ChunkLoop]:
    """Make circuit chunks for Y-basis measurement."""
    boundary_patch = _make_yboundary_degenerate_patch(
        distance, top_boundary_basis_before_measure, convention
    )
    qubit_to_boundary_round = _make_y_transition_round(
        distance, top_boundary_basis_before_measure, convention, include_observables
    )
    boundary_round = _standard_surface_code_chunk(boundary_patch)
    final_round = _standard_surface_code_chunk(
        boundary_patch,
        measure_data_basis=_get_final_measure_data_basis(
            boundary_patch.data_set, top_boundary_basis_before_measure, convention
        ),
    )
    if not include_open_flows:
        qubit_to_boundary_round = _without_in_det_flows(qubit_to_boundary_round)
    if close_obs_flows:
        det_flows = [f for f in qubit_to_boundary_round.flows if f.obs_key is None]
        obs_flows = [f for f in qubit_to_boundary_round.flows if f.obs_key is not None]
        closed_obs_flows = [f.with_edits(start=gen.PauliMap({})) for f in obs_flows]
        qubit_to_boundary_round = qubit_to_boundary_round.with_edits(
            flows=det_flows + closed_obs_flows
        )
    return [
        qubit_to_boundary_round.with_transformed_coords(transform),
        boundary_round.with_transformed_coords(transform).with_repetitions(padding_rounds),
        final_round.with_transformed_coords(transform),
    ]


def _get_final_measure_data_basis(
    data_qubits: Set[complex],
    top_boundary_basis_before_transition: Basis,
    convention: Literal["fixed_boundary", "fixed_bulk"],
) -> dict[complex, str]:
    if top_boundary_basis_before_transition == Basis.Z:
        return {q: "Z" if q.real < q.imag else "X" for q in data_qubits}
    if convention == "fixed_bulk":
        return {q: "X" if q.real <= q.imag else "Z" for q in data_qubits}
    return {q: "X" if q.real < q.imag else "Z" for q in data_qubits}


def _make_y_basis_initialization_chunks(
    distance: int,
    top_boundary_basis_after_init: Basis,
    convention: Literal["fixed_boundary", "fixed_bulk"],
    padding_rounds: int,
    transform: Callable[[complex], complex] = lambda x: x,
    include_observables: Iterable[int] = (0,),
    close_obs_flows: bool = False,
    include_open_flows: bool = True,
) -> list[gen.Chunk | gen.ChunkLoop]:
    """Make circuit chunks for Y-basis initialization."""
    qubit_to_boundary_round, boundary_rounds, final_round = _make_y_basis_measurement_chunks(
        distance,
        top_boundary_basis_after_init,
        convention,
        padding_rounds,
        transform=transform,
        include_observables=include_observables,
        close_obs_flows=False,
        include_open_flows=include_open_flows,
    )
    boundary_to_qubit_round = qubit_to_boundary_round.time_reversed()
    if close_obs_flows:
        assert isinstance(boundary_to_qubit_round, gen.Chunk)
        det_flows = [f for f in boundary_to_qubit_round.flows if f.obs_key is None]
        obs_flows = [f for f in boundary_to_qubit_round.flows if f.obs_key is not None]
        closed_obs_flows = [f.with_edits(end=gen.PauliMap({})) for f in obs_flows]
        boundary_to_qubit_round = boundary_to_qubit_round.with_edits(
            flows=det_flows + closed_obs_flows
        )
    return [
        final_round.time_reversed(),
        boundary_rounds.time_reversed(),
        boundary_to_qubit_round,
    ]


def _without_in_det_flows(chunk: gen.Chunk) -> gen.Chunk:
    """Return a copy of the chunk with all input flows removed."""
    kept_flows = [flow for flow in chunk.flows if not flow.start or flow.obs_key is not None]
    return chunk.with_edits(flows=kept_flows)


def _make_y_basis_init_or_meas_interface(
    distance: int,
    top_boundary_basis: Basis,
    convention: Literal["fixed_boundary", "fixed_bulk"],
    transform: Callable[[complex], complex] = lambda x: x,
) -> gen.ChunkInterface:
    """Make the start/end chunk interface for Y-basis measurement/initialization."""
    qubit_to_boundary_round = _make_y_transition_round(distance, top_boundary_basis, convention)
    flows = qubit_to_boundary_round.flows
    det_flows = [f for f in flows if f.obs_key is None]

    det_interface = gen.ChunkInterface(
        ports=[flow.key_start for flow in det_flows if flow.start],
    ).with_transformed_coords(transform)
    return det_interface


def get_y_half_cube_block(
    y_spec: YHalfCubeSpec, convention: Literal["fixed_bulk", "fixed_boundary"]
) -> InjectedBlock:
    """Get a chunks factory for Y-basis initialization and measurement circuit."""
    top_boundary_basis = y_spec.horizontal_boundary_basis

    def scale_transform(q: complex) -> complex:
        """Transform the coordinates to match the scale used in TQEC."""
        return 2 * q + 1 + 1j

    def factory(k: int, annotate_observables: list[int] | None = None) -> CircuitWithInterface:
        distance = 2 * k + 1
        padding_rounds = distance // 2
        if y_spec.initialization:
            chunks = _make_y_basis_initialization_chunks(
                distance,
                top_boundary_basis_after_init=top_boundary_basis,
                convention=convention,
                padding_rounds=padding_rounds,
                transform=scale_transform,
                include_observables=annotate_observables or [],
                close_obs_flows=True,
                include_open_flows=False,
            )
        else:
            chunks = _make_y_basis_measurement_chunks(
                distance,
                top_boundary_basis_before_measure=top_boundary_basis,
                convention=convention,
                padding_rounds=padding_rounds,
                transform=scale_transform,
                include_observables=annotate_observables or [],
                close_obs_flows=True,
                include_open_flows=False,
            )
        circuit = gen.compile_chunks_into_circuit(chunks)  # type: ignore[arg-type]
        det_interface = _make_y_basis_init_or_meas_interface(
            distance, top_boundary_basis, convention, scale_transform
        )
        return CircuitWithInterface(circuit, det_interface)

    return InjectedBlock(
        factory,
        scalable_timesteps=LinearFunction(1, 2),
        scalable_shape=PhysicalQubitScalable2D(x=LinearFunction(4, 5), y=LinearFunction(4, 5)),
        alignment=Alignment.TAIL if y_spec.initialization else Alignment.HEAD,
    )
