"""Factory for Y basis initialization and measurement circuit."""

import functools
from collections.abc import Callable, Iterable

import gen

DIRS: list[complex] = [(1 + 1j) * 1j**d for d in range(4)]
DR, DL, UL, UR = DIRS
HORIZONTAL_HOOK_ORDER = [UL, UR, DL, DR]
VERTICAL_HOOK_ORDER = [UL, DL, UR, DR]


def surface_code_patch(
    *,
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


def checkerboard_basis(q: complex, top_left_tile_basis: str) -> str:
    """Classifies a coordinate as X type or Z type according to a checkerboard."""
    tlb_flipped = "Z" if top_left_tile_basis == "X" else "X"
    return top_left_tile_basis if int(q.real + q.imag) % 4 == 0 else tlb_flipped


def rectangular_surface_code_patch(
    *,
    width: int,
    height: int,
    top_basis: str,
    bot_basis: str,
    left_basis: str,
    right_basis: str,
    top_left_tile_basis: str,
    order_func: Callable[[complex], Iterable[complex | None]],
) -> gen.Patch:
    """Make a rectangular surface code patch."""

    def is_boundary(m: complex, *, b: str) -> bool:
        if top_basis == b and m.imag == 0:
            return True
        if left_basis == b and m.real == 0:
            return True
        if bot_basis == b and m.imag == 2 * height:
            return True
        if right_basis == b and m.real == 2 * width:
            return True
        return False

    return surface_code_patch(
        possible_data_qubits=[
            (1 + 1j) + 2 * x + 2j * y for x in range(width) for y in range(height)
        ],
        basis=functools.partial(checkerboard_basis, top_left_tile_basis=top_left_tile_basis),
        is_boundary_x=functools.partial(is_boundary, b="X"),
        is_boundary_z=functools.partial(is_boundary, b="Z"),
        order_func=order_func,
    )


def order_func(m: complex, top_bot_basis: str) -> list[complex]:
    """Determine the interaction order for a data qubit with the surrounding measure qubits."""
    if checkerboard_basis(m, top_left_tile_basis="Z") == top_bot_basis:
        return HORIZONTAL_HOOK_ORDER
    return VERTICAL_HOOK_ORDER


def make_fixed_bulk_qubit_patch(
    *,
    distance: int,
    top_bot_basis: str,
) -> gen.Patch:
    """Make a rectangular surface code patch with fixed bulk convention."""
    left_right_basis = "Z" if top_bot_basis == "X" else "X"
    return rectangular_surface_code_patch(
        width=distance,
        height=distance,
        top_basis=top_bot_basis,
        right_basis=left_right_basis,
        bot_basis=top_bot_basis,
        left_basis=left_right_basis,
        top_left_tile_basis="Z",
        order_func=functools.partial(order_func, top_bot_basis=top_bot_basis),
    )


def make_fixed_boundary_qubit_patch(
    *,
    distance: int,
    top_bot_basis: str,
) -> gen.Patch:
    """Make a rectangular surface code patch with fixed boundary convention."""
    left_right_basis = "Z" if top_bot_basis == "X" else "X"
    return rectangular_surface_code_patch(
        width=distance,
        height=distance,
        top_basis=top_bot_basis,
        right_basis=left_right_basis,
        bot_basis=top_bot_basis,
        left_basis=left_right_basis,
        top_left_tile_basis=top_bot_basis,
        order_func=functools.partial(order_func, top_bot_basis=top_bot_basis),
    )


def make_fixed_bulk_yboundary_patch(
    *,
    distance: int,
    top_bot_basis_after_transition: str,
) -> gen.Patch:
    """Make a surface code patch at the time boundary of Y-basis initialization
    with fixed bulk convention.
    """
    return rectangular_surface_code_patch(
        width=distance,
        height=distance,
        top_basis="Z",
        right_basis="X",
        bot_basis="X",
        left_basis="Z",
        top_left_tile_basis="Z",
        order_func=functools.partial(order_func, top_bot_basis=top_bot_basis_after_transition),
    )


def make_fixed_boundary_yboundary_patch(
    *,
    distance: int,
    top_bot_basis_after_transition: str,
) -> gen.Patch:
    """Make a surface code patch at the time boundary of Y-basis initialization
    with fixed boundary convention.
    """
    top_left_basis = "Z" if top_bot_basis_after_transition == "Z" else "X"
    bot_right_basis = "Z" if top_left_basis == "X" else "X"
    return rectangular_surface_code_patch(
        width=distance,
        height=distance,
        top_basis=top_left_basis,
        right_basis=bot_right_basis,
        bot_basis=bot_right_basis,
        left_basis=top_left_basis,
        top_left_tile_basis=top_left_basis,
        order_func=functools.partial(order_func, top_bot_basis=top_bot_basis_after_transition),
    )
