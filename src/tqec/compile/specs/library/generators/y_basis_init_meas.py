"""Factory for Y basis initialization and measurement circuit."""

import functools
from collections.abc import Callable, Iterable, Set
from typing import Any, Literal

import gen

from tqec.compile.blocks.injected_block import Alignment, InjectedBlock
from tqec.compile.specs.base import YHalfCubeSpec
from tqec.utils.scale import LinearFunction, PhysicalQubitScalable2D

DIRS: list[complex] = [(0.5 + 0.5j) * 1j**d for d in range(4)]
DR, DL, UL, UR = DIRS
ORDER_S = [UR, UL, DR, DL]
ORDER_N = [UR, DR, UL, DL]


def surface_code_patch(
    possible_data_qubits: Iterable[complex],
    basis: Callable[[complex], str],
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
        if is_boundary_x(m) <= (basis(m) == "X")
        if is_boundary_z(m) <= (basis(m) == "Z")
    }
    data_qubits = {
        q for q in possible_data_qubits if sum(q + d in measure_qubits for d in DIRS) > 1
    }

    tiles = [
        gen.Tile(
            bases=basis(m),
            data_qubits=[
                m + d if d is not None and m + d in data_qubits else None for d in order_func(m)
            ],
            measure_qubit=m,
        )
        for m in measure_qubits
    ]
    return gen.Patch(tiles)


def checkerboard_basis(q: complex) -> str:
    """Classifies a coordinate as X type or Z type according to a checkerboard."""
    is_x = int(q.real + q.imag) & 1 == 0
    return "X" if is_x else "Z"


def rectangular_surface_code_patch(
    width: int,
    height: int,
    top_basis: str,
    bot_basis: str,
    left_basis: str,
    right_basis: str,
    order_func: Callable[[complex], Iterable[complex | None]],
) -> gen.Patch:
    """Make a rectangular surface code patch."""

    def is_boundary(m: complex, *, b: str) -> bool:
        if top_basis == b and m.imag == -0.5:
            return True
        if left_basis == b and m.real == -0.5:
            return True
        if bot_basis == b and m.imag == height - 0.5:
            return True
        if right_basis == b and m.real == width - 0.5:
            return True
        return False

    return surface_code_patch(
        possible_data_qubits=[x + 1j * y for x in range(width) for y in range(height)],
        basis=checkerboard_basis,
        is_boundary_x=functools.partial(is_boundary, b="X"),
        is_boundary_z=functools.partial(is_boundary, b="Z"),
        order_func=order_func,
    )


def make_xtop_qubit_patch(distance: int) -> gen.Patch:
    """Make a surface code patch with X boundaries on top and bottom edges."""

    def order_func(m: complex) -> list[complex]:
        if checkerboard_basis(m) == "X":
            return ORDER_S
        else:
            return ORDER_N

    return rectangular_surface_code_patch(
        width=distance,
        height=distance,
        top_basis="X",
        right_basis="Z",
        bot_basis="X",
        left_basis="Z",
        order_func=order_func,
    )


def make_ztop_yboundary_patch(distance: int) -> gen.Patch:
    """Make the surface code patch at the end of a Y-basis measurement."""

    def order_func(m: complex) -> list[complex]:
        if checkerboard_basis(m) == "X":
            return ORDER_S
        else:
            return ORDER_N

    return rectangular_surface_code_patch(
        width=distance,
        height=distance,
        top_basis="Z",
        right_basis="X",
        bot_basis="X",
        left_basis="Z",
        order_func=order_func,
    )


def build_surface_code_round_circuit(
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


def standard_surface_code_chunk(
    patch: gen.Patch,
    init_data_basis: str | dict[complex, str] | None = None,
    measure_data_basis: str | dict[complex, str] | None = None,
    obs: gen.PauliMap | None = None,
    wants_to_merge_with_prev: bool = False,
    wants_to_merge_with_next: bool = False,
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
    build_surface_code_round_circuit(
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

    return builder.finish_chunk(
        wants_to_merge_with_prev=wants_to_merge_with_prev,
        wants_to_merge_with_next=wants_to_merge_with_next,
    )


def _m_basis(m: complex) -> str | None:
    if m.real % 1 == 0:
        return None
    is_x = int(m.real + m.imag) & 1 == 0
    return "X" if is_x else "Z"


def _split_dl_md_ur(ps: Set[complex]) -> tuple[set[complex], set[complex], set[complex]]:
    dl = set()
    ur = set()
    md = set()
    for m in ps:
        dst = ur if m.real > m.imag + 1 else md if m.real == m.imag or m.real == m.imag + 1 else dl
        dst.add(m)
    return dl, md, ur


def make_y_transition_round_nesw_xzxz_to_xzzx(distance: int) -> gen.Chunk:
    """Make the circuit chunk for surface code patch transition from XZXZ to XZZX boundaries."""
    start = make_xtop_qubit_patch(distance)
    end = make_ztop_yboundary_patch(distance)
    used = start.used_set | end.used_set

    xs = {q for q in used if _m_basis(q) == "X"}
    zs = {q for q in used if _m_basis(q) == "Z"}
    top_row = {q for q in used if q.imag == -0.5}
    right_col = {q for q in used if q.real == distance - 0.5}

    def toward(qs: Set[complex], delta: complex, sign: int) -> set[tuple[complex, complex]]:
        result = set()
        for q in qs:
            if q + delta in used:
                result.add((q, q + delta)[::sign])
        return result

    xs_dl, xs_md, xs_ur = _split_dl_md_ur(xs)
    zs_dl, zs_md, zs_ur = _split_dl_md_ur(zs)

    builder = gen.ChunkBuilder(used)
    builder.append("RX", (xs - right_col) | top_row)
    builder.append("R", (zs - top_row) | right_col)
    builder.append("TICK")
    builder.append("CX", toward(xs - right_col, DL, +1))
    builder.append("CX", toward(zs - top_row, DL, -1))
    builder.append("TICK")
    builder.append("CX", toward(xs - right_col, DR, +1))
    builder.append("CX", toward(zs - top_row, UL, -1))
    builder.append("TICK")
    builder.append("CX", toward(xs_ur | xs_md, UL, -1))
    builder.append("CX", toward(zs_ur, DR, +1))
    builder.append("XCY", toward(zs_md, DR, +1))
    builder.append("CX", toward(xs_dl, UL, +1))
    builder.append("CX", toward(zs_dl, DR, -1))
    builder.append("TICK")
    builder.append("CX", toward(xs_ur, DL, -1))
    builder.append("CX", toward(zs_ur, DL, +1))
    builder.append("CX", toward(xs_dl, UR, +1))
    builder.append("CX", toward(zs_dl, UR, -1))
    builder.append("TICK")
    builder.append("XCY", toward(xs_md - top_row, DL, -1))
    builder.append("TICK")
    builder.append("H", [q for q in used if q.real > q.imag])
    builder.append("SQRT_X", [q for q in used if q.real == q.imag and q.real % 1 == 0.5])
    builder.append("TICK")
    xms = (xs - top_row) | right_col

    def measure_key_func(pos: complex) -> tuple[complex, Any]:
        return (pos, "solo")

    builder.append("MX", xms, measure_key_func=measure_key_func)
    builder.append("MY", {0}, measure_key_func=measure_key_func)
    builder.append("MZ", (zs - right_col) | top_row, measure_key_func=measure_key_func)

    # Annotate input stabilizers that get measured.
    for tile in start.tiles:
        m = tile.measure_qubit
        assert m is not None
        if m.real == m.imag:
            measurements = [m, m + 1]
        elif m.real == distance - 0.5:
            measurements = [m]
        elif m.imag == -0.5:
            measurements = [m]
        elif m.real > m.imag and tile.basis == "X":
            measurements = [m - 1j]
        elif m.real > m.imag and tile.basis == "Z":
            measurements = [m + 1]
        elif m.real < m.imag:
            measurements = [m]
        else:
            raise NotImplementedError(f"{m=!r}")

        builder.add_flow(
            start=tile.to_pauli_map(),
            center=m,
            ms=[(k, "solo") for k in measurements],
        )

    # Annotate output stabilizers that get prepared.
    for tile in end.tiles:
        m = tile.measure_qubit
        assert m is not None
        if m == 0.5 + 0.5j:
            measurements = [m, m + 1, m - 1j, m + UL]
        elif m == distance - 0.5 + 0.5j:
            measurements = [m]
        elif m == distance - 1.5 - 0.5j:
            measurements = [m]
        elif m.real == distance - 0.5:
            measurements = [m, m - 1j]
        elif m.imag == -0.5:
            measurements = [m, m + 1]
        elif m.real == m.imag:
            measurements = [m, m + 1, m - 1j]
        else:
            measurements = [m]

        builder.add_flow(
            end=tile.to_pauli_map(),
            center=m,
            ms=[(k, "solo") for k in measurements],
        )

    # Annotate how observable flows through the system.
    # Contrast to the observable in the paper, the annotated observable is composed
    # of the two X/Z midline operators.
    half_d = distance // 2
    center_dq = complex(half_d, half_d)
    builder.add_flow(
        center=center_dq,
        start=gen.PauliMap(
            {
                center_dq: "Y",
                **{complex(q, half_d): "Z" for q in range(distance) if q != half_d},
                **{complex(half_d, q): "X" for q in range(distance) if q != half_d},
            }
        ),
        ms=[
            (m, "solo")
            for m in [
                0j,
                *[q for q in zs | top_row if q.real < half_d and q.imag < half_d],
                *[q for q in xs | right_col if q.real > half_d and q.imag > half_d],
            ]
        ],
        obs_key=0,
    )

    return builder.finish_chunk()


def make_y_basis_measurement_chunks(
    distance: int,
    padding_rounds: int,
    transform: Callable[[complex], complex] = lambda x: x,
) -> list[gen.Chunk | gen.ChunkLoop]:
    """Make circuit chunks for Y-basis measurement."""
    boundary_patch = make_ztop_yboundary_patch(distance=distance)
    qubit_to_boundary_round = make_y_transition_round_nesw_xzxz_to_xzzx(distance=distance)
    boundary_round = standard_surface_code_chunk(boundary_patch)
    final_round = standard_surface_code_chunk(
        boundary_patch,
        measure_data_basis={
            q: "Z" if q.real + q.imag < distance else "X" for q in boundary_patch.data_set
        },
    )
    return [
        qubit_to_boundary_round.with_transformed_coords(transform),
        boundary_round.with_transformed_coords(transform).with_repetitions(padding_rounds),
        final_round.with_transformed_coords(transform),
    ]


def make_y_basis_initialization_chunks(
    distance: int,
    padding_rounds: int,
    transform: Callable[[complex], complex] = lambda x: x,
) -> list[gen.Chunk | gen.ChunkLoop]:
    """Make circuit chunks for Y-basis initialization."""
    qubit_to_boundary_round, boundary_rounds, final_round = make_y_basis_measurement_chunks(
        distance, padding_rounds, transform
    )
    return [
        final_round.time_reversed(),
        boundary_rounds.time_reversed(),
        qubit_to_boundary_round.time_reversed(),
    ]


def transform_qubit_to_patch_orientation(
    qubit: complex,
    center: complex,
    convention: Literal["fixed_bulk", "fixed_boundary"],
    top_bot_boundary_basis: str,
) -> complex:
    """Transform the patch coordinates of the Y-basis init/meas chunks into the
    correct orientation for the certain boundary conditions and convention. The
    qubit coordinates are scaled at the end to be on the integer lattice.
    """

    def scale(q: complex) -> complex:
        return 2 * q + 1 + 1j

    def reflect_across_vertical_axis(q: complex) -> complex:
        return complex(2 * center.real - q.real, q.imag)

    def rotate_90_clockwise(q: complex) -> complex:
        qr = center.real + (center.imag - q.imag)
        qi = center.imag + (q.real - center.real)
        return complex(qr, qi)

    # The original patch has X boundaries on top and bottom and conforms to the
    # "fixed_bulk" convention.
    match convention, top_bot_boundary_basis:
        case _, "Z":
            # rotate 90 degrees clockwise, then reflect across vertical axis
            print(rotate_90_clockwise(qubit))
            return scale(reflect_across_vertical_axis(rotate_90_clockwise(qubit)))
        case "fixed_boundary", "X":
            # reflect across vertical axis
            return scale(reflect_across_vertical_axis(qubit))
        case _:  # "fixed_bulk", "X"
            return scale(qubit)


def get_y_half_cube_block(
    y_spec: YHalfCubeSpec, convention: Literal["fixed_bulk", "fixed_boundary"]
) -> InjectedBlock:
    """Get a chunks factory for Y-basis initialization and measurement circuit."""

    def factory(k: int) -> list[gen.Chunk | gen.ChunkLoop]:
        distance = 2 * k + 1
        padding_rounds = distance // 2
        center = complex(distance // 2, distance // 2)
        transform = functools.partial(
            transform_qubit_to_patch_orientation,
            center=center,
            convention=convention,
            top_bot_boundary_basis=str(y_spec.horizontal_boundary_basis),
        )
        func = (
            make_y_basis_initialization_chunks
            if y_spec.initialization
            else make_y_basis_measurement_chunks
        )
        return func(
            distance=distance,
            padding_rounds=padding_rounds,
            transform=transform,
        )

    return InjectedBlock(
        factory,
        scalable_timesteps=LinearFunction(1, 2),
        scalable_shape=PhysicalQubitScalable2D(x=LinearFunction(4, 5), y=LinearFunction(4, 5)),
        alignment=Alignment.TAIL if y_spec.initialization else Alignment.HEAD,
    )
