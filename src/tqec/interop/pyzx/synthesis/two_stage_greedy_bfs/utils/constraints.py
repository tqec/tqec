from tqec.interop.pyzx.synthesis.two_stage_greedy_bfs.utils.utils import check_is_exit


def check_face_match(
    source_coord: tuple, source_kind: str, target_coord: tuple, target_kind: str
):
    """
    Checks if a block or pipe has an available exit pointing towards a target coordinate.
    To use this functoin to check if two cubes match, run it twice: one from current to target and one from target to current.

    ! Note. Function does not test if target coordinate is available.
    ! Note. Function does not test if exit is unobstructed.

    Args:
        - source_coord: (x, y, z) coordinates for source node
        - source_kind: kind for the source node
        - target_coord: (x, y, z) coordinates for target node

    Returns:
        - bool: True if source node is open to the side of the target coordinate, else False.
    """

    # Sanitise kind in case of mixed case inputs
    source_kind = source_kind.lower()[:3]
    target_kind = target_kind.lower()[:3]

    # Extract axis of displacement from kinds
    displacements = [p[1] - p[0] for p in list(zip(source_coord, target_coord))]
    axis_displacement = [True if axis != 0 else False for axis in displacements]

    idx = axis_displacement.index(True)

    new_source_kind = source_kind[:idx] + source_kind[idx + 1 :]
    new_target_kind = target_kind[:idx] + target_kind[idx + 1 :]

    # Fail if two other dimensions do not match
    if not new_source_kind == new_target_kind:
        return False

    # Pass otherwise
    return True


def check_cube_match(
    current_pos: tuple, current_kind: str, next_pos: tuple, next_kind: str
):
    """
    Checks if two cubes match.

    ! Note. Function does not handle HADAMARDS... Yet

    Args:
        - current_pos: (x, y, z) coordinates for the current node
        - current_kind: current node's kind
        - next_pos: (x, y, z) coordinates for the next node
        - next_kind: target node's kind

    Returns:
        - bool: True if the cubes match, else False.
    """

    # SANITISE
    current_kind = current_kind.lower()
    next_kind = next_kind.lower()

    # CHECK SOURCE TO TARGET
    # Connection takes place on a valid exit of source
    if not check_is_exit(current_pos, current_kind, next_pos):
        return False

    # CHECK TARGET TO SOURCE
    # Connection takes place on a valid exit of target
    if not check_is_exit(next_pos, next_kind, current_pos):
        return False

    return True


def get_valid_next_kinds(current_pos, current_kind, next_pos):
    # HELPER VARIABLES
    possible_kinds = []
    all_cube_kinds = ["xxz", "xzz", "xzx", "zzx", "zxx", "zxz"]
    all_pipe_kinds = [
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

    # CHECK FOR ALL POSSIBLE NEXT KINDS IN DISPLACEMENT AXIS
    # If current kind has an "o", the next kind is a cube
    if "o" in current_kind:
        for next_kind in all_cube_kinds:
            cube_match = check_cube_match(
                current_pos, current_kind, next_pos, next_kind
            )
            if cube_match:
                possible_kinds.append(next_kind)

    # If current kind does not have an "o", then current kind is cube and the next kind is a pipe
    else:
        for next_kind in all_pipe_kinds:
            cube_match = check_cube_match(
                current_pos, current_kind, next_pos, next_kind
            )
            if cube_match:
                possible_kinds.append(next_kind)

    # Now discard possible kinds where there is no colour match for all non-connection faces
    reduced_possible_kinds = []
    for next_kind in possible_kinds:
        if check_face_match(current_pos, current_kind, next_pos, next_kind):
            reduced_possible_kinds.append(next_kind)

    # RETURN ARRAY OF POSSIBLE NEXT KINDS
    return reduced_possible_kinds
