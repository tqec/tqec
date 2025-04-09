import random
from typing import Tuple, List, Dict, Optional, Any


def zx_types_validity_checks(graph: Dict[str, List[Any]]) -> bool:
    valid_types: List[str] = ["X", "Y", "Z", "O", "SIMPLE", "HADAMARD"]
    valid_types_lower = [key.lower() for key in [t.lower() for t in valid_types]]
    nodes_data: List[Tuple[int, str]] = graph.get("nodes", [])
    for _, node_type in nodes_data:
        if node_type.lower() not in valid_types_lower:
            print(f"Error: Node type '{node_type}' is not valid.")
            return False
    return True


def get_type_family(node_type: str) -> Optional[List[str]]:
    families: Dict[str, List[str]] = {
        "X": ["xxz", "xzx", "zxx"],
        "Y": ["yyy"],
        "Z": ["xzz", "zzx", "zxz"],
        "O": ["ooo"],
        "SIMPLE": ["zxo", "xzo", "oxz", "ozx", "xoz", "zox"],
        "HADAMARD": ["zxoh", "xzoh", "oxzh", "ozxh", "xozh", "zoxh"],
    }

    if node_type not in families:
        print(
            f"Warning: Node type '{node_type}' not found in kind families."
        )  # Potential Issue: Handle missing node type
        return None
    return families[node_type]


def check_is_exit(source_coord: tuple, source_kind: str, target_coord: tuple):
    source_kind = source_kind.lower()[:3]
    kind_3D = [source_kind[0], source_kind[1], source_kind[2]]

    if "o" in kind_3D:
        exit_marker = "o"
    else:
        exit_marker = [i for i in set(kind_3D) if kind_3D.count(i) == 2][0]

    valid_exit_indices = [i for i, char in enumerate(kind_3D) if char == exit_marker]
    displacements = [
        target - source for source, target in zip(source_coord, target_coord)
    ]

    displacement_axis_index = -1
    for i, disp in enumerate(displacements):
        if disp != 0:
            displacement_axis_index = i
            break

    if displacement_axis_index != -1 and displacement_axis_index in valid_exit_indices:
        return True
    else:
        return False


def check_unobstructed(
    source_coord: tuple,
    target_coord: tuple,
    occupied: list[tuple],
    beams: list[tuple],
    beam_length=3,
):
    add_beams = []

    directions = [target - source for source, target in zip(source_coord, target_coord)]
    directions = [1 if d > 0 else -1 if d < 0 else 0 for d in directions]

    for i in range(1, beam_length):
        dx, dy, dz = (directions[0] * i, directions[1] * i, directions[2] * i)
        add_beams.append(
            (source_coord[0] + dx, source_coord[1] + dy, source_coord[2] + dz)
        )

    if not occupied:
        return True, add_beams

    for coord in add_beams:
        if coord in occupied or coord in beams:
            return False, add_beams

    return True, add_beams


def check_for_exits(node_coords, node_kind, occupied, all_beams):
    unobstructed_exits_n = 0
    node_beams = []

    directional_array = [
        (1, 0, 0),
        (-1, 0, 0),
        (0, 1, 0),
        (0, -1, 0),
        (0, 0, 1),
        (0, 0, -1),
    ]

    for d in directional_array:
        target_coords = (
            node_coords[0] + d[0],
            node_coords[1] + d[1],
            node_coords[2] + d[2],
        )

        if check_is_exit(node_coords, node_kind, target_coords):
            is_unobstructed, exit_beam = check_unobstructed(
                node_coords, target_coords, occupied, all_beams
            )
            if is_unobstructed:
                unobstructed_exits_n += 1
                node_beams.append(exit_beam)

    return unobstructed_exits_n, node_beams


def is_move_allowed(
    source_coords: Tuple[int, int, int], next_coords: Tuple[int, int, int]
) -> bool:
    sx, sy, sz = source_coords
    nx, ny, nz = next_coords
    manhattan_distance = abs(nx - sx) + abs(ny - sy) + abs(nz - sz)
    return manhattan_distance % 3 == 0


def generate_tentative_target_positions(
    source_coords: Tuple[int, int, int],
    step: int = 3,
    occupied_coords: List[Tuple[int, int, int]] = [],
) -> List[Tuple[int, int, int]]:
    # EXTRACT SOURCE COORDS
    sx, sy, sz = source_coords
    potential_targets = []

    # SINGLE MOVES
    if step == 3:
        targets = [
            (sx + 3, sy, sz),
            (sx - 3, sy, sz),
            (sx, sy + 3, sz),
            (sx, sy - 3, sz),
            (sx, sy, sz + 3),
            (sx, sy, sz - 3),
        ]
        potential_targets = [
            coords for coords in targets if coords not in occupied_coords
        ]

    # DOUBLE MOVES (Manhattan distance 6)
    elif step == 6:
        targets = set()
        for dx in [-3, 3]:
            for dy in [-3, 3]:
                targets.add((sx + dx, sy + dy, sz))
            for dx in [-3, 3]:
                for dz in [-3, 3]:
                    targets.add((sx + dx, sy, sz + dz))
            for dy in [-3, 3]:
                for dz in [-3, 3]:
                    targets.add((sx, sy + dy, sz + dz))
        potential_targets = [
            coords for coords in targets if coords not in occupied_coords
        ]

    # TRIPLE MOVES (Manhattan distance 9)
    elif step == 9:
        targets = set()
        for dx in [-3, 3]:
            for dy in [-3, 3]:
                for dz in [-3, 3]:
                    if abs(dx) + abs(dy) + abs(dz) == 9:
                        targets.add((sx + dx, sy + dy, sz + dz))
        potential_targets = [
            coords for coords in targets if coords not in occupied_coords
        ]

    # ANY STEP HIGHER THAN 9 (step is Manhattan distance, multiple of 3)
    elif step > 9 and step % 3 == 0:
        valid_targets = set()
        attempts = 0
        max_attempts = 500  # Limit attempts to avoid infinite loops in dense spaces
        while len(valid_targets) < 12 and attempts < max_attempts:
            remaining_steps = step
            current_x = sx
            current_y = sy
            current_z = sz

            # Move along x
            move_x = random.choice(range(-remaining_steps, remaining_steps + 1, 3))
            current_x += move_x
            remaining_steps -= abs(move_x)

            # Move along y
            move_y = random.choice(range(-remaining_steps, remaining_steps + 1, 3))
            current_y += move_y
            remaining_steps -= abs(move_y)

            # Move along z (remaining distance)
            move_z = remaining_steps
            current_z += move_z

            if (
                abs(move_x) + abs(move_y) + abs(move_z) == step
                and (current_x, current_y, current_z) not in occupied_coords
            ):
                valid_targets.add((current_x, current_y, current_z))

            # Try other permutations of moves
            permutations = [
                (move_x, move_y, move_z),
                (move_x, move_z, move_y),
                (move_y, move_x, move_z),
                (move_y, move_z, move_x),
                (move_z, move_x, move_y),
                (move_z, move_y, move_x),
            ]

            for mx, my, mz in permutations:
                cx, cy, cz = sx + mx, sy + my, sz + mz
                if (
                    abs(mx) + abs(my) + abs(mz) == step
                    and (cx, cy, cz) not in occupied_coords
                ):
                    valid_targets.add((cx, cy, cz))

            attempts += 1

        potential_targets = list(valid_targets)

    return potential_targets


### THIS ONE NEEDS TO BE DELETED... I THINK... BEST TO CHECK AGAIN
def get_next_type(current_type, displacement):
    if "o" in current_type:
        possible_types = ["xxz", "xzz", "xzx", "zzx", "zxx", "zxz"]
        return possible_types
    else:
        possible_types = [
            "zxo",
            "xzo",
            "oxz",
            "ozx",
            "xoz",
            "zox",
            "zxoh",
            "xzoh",
            "oxzh",
            "ozxh",
            "xozh",
            "zoxh",
        ]
        return possible_types
