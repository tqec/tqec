from collections import deque
from tqec.interop.pyzx.synthesis.two_stage_greedy_bfs.utils.utils import is_move_allowed
from tqec.interop.pyzx.synthesis.two_stage_greedy_bfs.utils.constraints import (
    get_valid_next_kinds,
)
from typing import List, Tuple, Union


def bfs_extended_3d(
    source_node: List[Union[Tuple[int, int, int], str]],
    target_node: List[Union[Tuple[int, int, int], str]],
    obstacle_coords_from_preexistent_structure=[],
):
    # Unpack information for source and target nodes
    start_coords, start_type = source_node
    end_coords, end_type = target_node

    if start_coords in obstacle_coords_from_preexistent_structure:
        obstacle_coords_from_preexistent_structure.remove(start_coords)
    if end_coords in obstacle_coords_from_preexistent_structure:
        obstacle_coords_from_preexistent_structure.remove(end_coords)

    queue = deque([source_node])
    visited = {tuple(source_node): 0}  # Store shortest path length to visited states
    path_length = {tuple(source_node): 0}
    path = {tuple(source_node): [source_node]}

    start_x, start_y, start_z = (int(x) for x in start_coords)
    end_x, end_y, end_z = (int(x) for x in end_coords)
    initial_manhattan_distance = (
        abs(start_x - end_x) + abs(start_y - end_y) + abs(start_z - end_z)
    )
    termination_distance = 6 * initial_manhattan_distance

    while queue:
        current_node_info = queue.popleft()
        current_coords, current_type = current_node_info
        x, y, z = (int(x) for x in current_coords)

        current_manhattan_distance = abs(x - end_x) + abs(y - end_y) + abs(z - end_z)
        if current_manhattan_distance > termination_distance:
            print("- Terminated.")
            return False, -1, None

        if current_coords == end_coords and (
            end_type == "ooo" or current_type == end_type
        ):
            print("- SUCCESS!")

            return (
                True,
                path_length[tuple(current_node_info)],
                path[tuple(current_node_info)],
            )

        scale = 2 if "o" in current_type else 1
        spatial_moves = [
            (1, 0, 0),
            (-1, 0, 0),
            (0, 1, 0),
            (0, -1, 0),
            (0, 0, 1),
            (0, 0, -1),
        ]

        for dx, dy, dz in spatial_moves:
            next_x, next_y, next_z = x + dx * scale, y + dy * scale, z + dz * scale
            next_coords = (next_x, next_y, next_z)
            current_path_coords = [node[0] for node in path[tuple(current_node_info)]]

            intermediate_pos = None
            if "o" in current_type and scale == 2:
                intermediate_x = x + dx * 1
                intermediate_y = y + dy * 1
                intermediate_z = z + dz * 1
                intermediate_pos = (intermediate_x, intermediate_y, intermediate_z)
                if (
                    intermediate_pos in current_path_coords
                    or intermediate_pos in obstacle_coords_from_preexistent_structure
                ):
                    continue

            possible_next_types = get_valid_next_kinds(
                current_coords, current_type, next_coords
            )

            for next_type in possible_next_types:
                next_node_info = [next_coords, next_type]
                next_state = tuple(next_node_info)

                if (
                    next_coords not in current_path_coords
                    and next_coords not in obstacle_coords_from_preexistent_structure
                    and (intermediate_pos is None or next_coords != intermediate_pos)
                ):
                    new_path_length = path_length[tuple(current_node_info)] + 1
                    if (
                        next_state not in visited
                        or new_path_length < visited[next_state]
                    ):
                        visited[next_state] = new_path_length
                        queue.append(next_node_info)
                        path_length[next_state] = new_path_length
                        path[next_state] = path[tuple(current_node_info)] + [
                            next_node_info
                        ]

    return False, -1, None


def determine_grid_size(start_coords, end_coords, obstacle_coords=[], margin=5):
    """
    Determines the bounding box of the search space.

    Returns: min_x, max_x, min_y, max_y, min_z, max_z
    """
    # print("\n\nCalculating bounding box.")
    all_coords = [start_coords, end_coords]
    if obstacle_coords:
        # print("Bounding box considers pre-existing structure.")
        all_coords.extend(obstacle_coords)
    else:
        pass
        # print("Bounding box based on start and end points.")

    min_x = min(coord[0] for coord in all_coords) - margin
    max_x = max(coord[0] for coord in all_coords) + margin
    min_y = min(coord[1] for coord in all_coords) - margin
    max_y = max(coord[1] for coord in all_coords) + margin
    min_z = min(coord[2] for coord in all_coords) - margin
    max_z = max(coord[2] for coord in all_coords) + margin

    return min_x, max_x, min_y, max_y, min_z, max_z


def generate_tentative_target_position(
    source_node: list,
    min_x: int,
    max_x: int,
    min_y: int,
    max_y: int,
    min_z: int,
    max_z: int,
    obstacle_coords: list = [],
    overwrite_target_coords: Tuple[int, int, int] | None = None,
    preexistent_structure: list = [],  # Add preexistent_structure as an argument
) -> Tuple[int, int, int] | None:
    """
    Generates a tentative target coordinate based on difficulty, checking validity with is_move_allowed.
    Uses a layered approach to prioritize closer targets.
    Ensures the target position is not in the preexistent structure.
    """
    if overwrite_target_coords:
        return overwrite_target_coords

    source_coords, source_type = source_node
    sx, sy, sz = source_coords
    # tentative_target_type = "xxz"
    preexistent_coords = [node[0] for node in preexistent_structure]

    # if obstacle_coords:
    # longest_side = max(max_x - min_x, max_y - min_y, max_z - min_z)
    # max_radius = min(longest_side + 4, 10)
    # else:
    # max_radius = 10

    # Level 1: Single Axis Displacement (+/- 3)
    potential_targets_level1 = [
        (sx + 3, sy, sz),
        (sx - 3, sy, sz),
        (sx, sy + 3, sz),
        (sx, sy - 3, sz),
        (sx, sy, sz + 3),
        (sx, sy, sz - 3),
    ]
    for tx, ty, tz in potential_targets_level1:
        if min_x <= tx <= max_x and min_y <= ty <= max_y and min_z <= tz <= max_z:
            if (tx, ty, tz) not in preexistent_coords and is_move_allowed(
                source_coords, (tx, ty, tz)
            ):
                print(f"=>> Returning potential target at Level 1: {(tx, ty, tz)}")
                return (tx, ty, tz)

    # Level 2: Two Axis Displacement (+/- 3 on two axes)
    potential_targets_level2 = []
    for dx in [-3, 3]:
        for dy in [-3, 3]:
            potential_targets_level2.extend(
                [(sx + dx, sy + dy, sz), (sx + dy, sy + dx, sz)]
            )
        for dz in [-3, 3]:
            potential_targets_level2.extend(
                [(sx + dx, sy, sz + dz), (sx + dz, sy, sz + dx)]
            )
        for dy in [-3, 3]:
            for dz in [-3, 3]:
                potential_targets_level2.extend(
                    [(sx, sy + dy, sz + dz), (sx, sy + dz, sz + dy)]
                )

    # Remove duplicates
    potential_targets_level2 = list(set(potential_targets_level2))

    for tx, ty, tz in potential_targets_level2:
        if min_x <= tx <= max_x and min_y <= ty <= max_y and min_z <= tz <= max_z:
            if (tx, ty, tz) not in preexistent_coords and is_move_allowed(
                source_coords, (tx, ty, tz)
            ):
                print(f"=>> Returning potential target at Level 2: {(tx, ty, tz)}")
                return (tx, ty, tz)

    # Level 3: Three Axis Displacement (+/- 3 on all three axes)
    potential_targets_level3 = []
    for dx in [-3, 3]:
        for dy in [-3, 3]:
            for dz in [-3, 3]:
                if dx != 0 or dy != 0 or dz != 0:  # Exclude the source itself
                    potential_targets_level3.append((sx + dx, sy + dy, sz + dz))

    for tx, ty, tz in potential_targets_level3:
        if min_x <= tx <= max_x and min_y <= ty <= max_y and min_z <= tz <= max_z:
            if (tx, ty, tz) not in preexistent_coords and is_move_allowed(
                source_coords, (tx, ty, tz)
            ):
                print(f"=>> Returning potential target at Level 3: {(tx, ty, tz)}")
                return (tx, ty, tz)

    print(
        "=> Could not generate a valid tentative target within the prioritized distances."
    )
    return None


def generate_tentative_target_types(target_node_zx_type, overwrite_target_type=None):
    if overwrite_target_type:
        return [overwrite_target_type]

    # NODE TYPE FAMILIES
    X = ["xxz", "xzx", "zxx"]
    Z = ["xzz", "zzx", "zxz"]
    BOUNDARY = ["ooo"]
    SIMPLE = ["zxo", "xzo", "oxz", "ozx", "xoz", "zox"]
    HADAMARD = ["zxoh", "xzoh", "oxzh", "ozxh", "xozh", "zoxh"]

    if target_node_zx_type in ["X", "Z"]:
        family = X if target_node_zx_type == "X" else Z
    elif target_node_zx_type == "O":
        family = BOUNDARY
    elif target_node_zx_type == "SIMPLE":
        family = SIMPLE
    elif target_node_zx_type == "HADAMARD":
        family = HADAMARD
    else:
        return [target_node_zx_type]

    return family


def obstacle_coords_from_preexistent_structure(preexistent_structure):
    """
    Converts a pre-existing structure (sequence of nodes) into a list of obstacle coordinates.
    Handles "o" type nodes which have a length of 2 based on the position relative to the previous node.
    """

    obstacle_coords = set()

    if not preexistent_structure:
        return []

    # Add the first node's coordinates
    first_node = preexistent_structure[0]
    if first_node:
        first_node_coords = first_node[0]
        obstacle_coords.add(first_node_coords)

    # Iterate from the second node
    for i in range(1, len(preexistent_structure)):
        current_node = preexistent_structure[i]
        prev_node = preexistent_structure[i - 1]
        if current_node and prev_node:
            current_node_coords, current_node_type = current_node
            prev_node_coords, prev_node_type = prev_node

            # Add current node's coordinates
            obstacle_coords.add(current_node_coords)

            if "o" in current_node_type and current_node_type != "ooo":
                cx, cy, cz = current_node_coords
                px, py, pz = prev_node_coords
                extended_coords = None

                if cx == px + 1:
                    extended_coords = (cx + 1, cy, cz)
                elif cx == px - 1:
                    extended_coords = (cx - 1, cy, cz)
                elif cy == py + 1:
                    extended_coords = (cx, cy + 1, cz)
                elif cy == py - 1:
                    extended_coords = (cx, cy - 1, cz)
                elif cz == pz + 1:
                    extended_coords = (cx, cy, cz + 1)
                elif cz == pz - 1:
                    extended_coords = (cx, cy, cz - 1)

                if extended_coords:
                    obstacle_coords.add(extended_coords)
                else:
                    print("Could not determine extended coords for 'o' type.")

    return list(obstacle_coords)


def run_bfs_for_all_potential_target_nodes(
    source_node,
    target_node_zx_type,
    distance,
    max_distance=18,
    attempts_per_distance=100,
    preexistent_structure=[],
    overwrite_target_node=[None, None],
    occupied_coords=[],
):
    """
    Runs BFS on a loop until path is found within predetermined distance of source node or max distance is reached.

    Args:
        - source_node: source node's coordinates (tuple) and type (str).
        - target_node_zx_type: ZX type of the target node, taken from a ZX chart.
        - distance: current allowed distance between source and target nodes.
        - max_distance: maximum allowed distance between source and target nodes.
        - attempts_per_distance: number of random target positions to try at each distance.

    """

    # HELPER VARIABLES
    all_paths_from_round = []
    start_coords, start_type = source_node
    min_path_length = None
    path_found = False
    length = None
    path = None
    found_path_at_current_distance = False
    overwrite_target_coords, overwrite_target_type = overwrite_target_node

    if preexistent_structure:
        obstacle_coords = obstacle_coords_from_preexistent_structure(
            preexistent_structure
        )

    obstacle_coords = []
    if occupied_coords:
        occupied_coords_copy = occupied_coords[:]
        if start_coords in occupied_coords_copy:
            obstacle_coords = occupied_coords_copy.remove(start_coords)
        else:
            obstacle_coords = occupied_coords_copy

    min_x_bb, max_x_bb, min_y_bb, max_y_bb, min_z_bb, max_z_bb = determine_grid_size(
        start_coords,
        overwrite_target_coords if overwrite_target_coords else (0, 0, 0),
        obstacle_coords=obstacle_coords,
    )

    # PATH FINDING LOOP W. MULTIPLE BFS ROUNDS WITH INCREASING DISTANCE FROM SOURCE NODE
    for attempt in range(attempts_per_distance):
        # Break if path is found in previous run of loop
        if distance > max_distance or path_found:
            break

        # Generate tentative position for target using the new function
        tentative_target_position = generate_tentative_target_position(
            source_node,
            min_x_bb,
            max_x_bb,
            min_y_bb,
            max_y_bb,
            min_z_bb,
            max_z_bb,
            obstacle_coords=obstacle_coords,
            overwrite_target_coords=overwrite_target_node[0],
            preexistent_structure=preexistent_structure,
        )

        if tentative_target_position is None:
            continue

        # Generate all possible target types at tentative position
        potential_target_types = generate_tentative_target_types(
            target_node_zx_type,
            overwrite_target_type=(
                overwrite_target_type if overwrite_target_type else None
            ),
        )

        # Find paths to all potential target kinds
        for potential_target_type in potential_target_types:
            target_node = [tentative_target_position, potential_target_type]
            candidate_path_found, candidate_length, candidate_path = bfs_extended_3d(
                source_node,
                target_node,
                obstacle_coords_from_preexistent_structure=(obstacle_coords),
            )

            # If path found, keep shortest path of round
            if candidate_path_found:
                path_found = True
                all_paths_from_round.append(candidate_path)
                if min_path_length is None or candidate_length < min_path_length:
                    min_path_length = candidate_length
                    length = candidate_length
                    path = candidate_path

        # Inform user of outcome at this distance
        if found_path_at_current_distance:
            path_found = True

        else:
            pass

        # Inform user of minimum length path, if found
        if min_path_length:
            pass

    # Return boolean for success of path finding, length of winner path, and winner path
    return path_found, length, path, all_paths_from_round
