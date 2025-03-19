"""Small True/False functions that test if a given aspect of a 3D graph meets a constraint needed validity.
Intended for, either, testing if an existing 3D graph is valid or building new 3D graphs.

"""

import numpy as np


def check_connection_n(neighbours: list[int]):
    """
    Checks that the total number of neighbours of a node is 4 or less.

    Args:
        - Neighbours: A list of neighbouring nodes (by node id)

    Returns:
        - bool: True if less than 5 nodes, else False.
    """

    # Straightforwardly check length of array and fail if longer than 4
    if len(neighbours) > 4:
        return False
    return True


def check_single_edge_is_2D(coord1, coord2):
    """
    Checks if an edge moves only in two dimensions
    (3D edges represent diagonal moves not possible in TQEC)

    Args:
        - coord1: (x, y, z) coordinates for the source node
        - coord2: (x, y, z) coordinates for the target node

    Returns:
        - bool: True if vector is straight, else False.
    """

    # zip coords for easier calculation
    zipped_coords = list(zip(coord1, coord2))

    # Calculate displacement from node
    xyz_distances = [pair[0] - pair[1] for pair in zipped_coords]

    # Filter displacement for items that are not a zero (i.e., axes with displacement)
    number_of_not_zeros = list(filter(lambda x: x != 0, xyz_distances))

    # Fail if there is displacement in more than one axis
    if len(number_of_not_zeros) > 1:
        return False

    # Pass otherwise
    return True


def check_valid_three_way(coord: tuple, connected_coords: list[tuple]):
    """
    Checks that the edges attached to a given node move in valid directions.

    ! Please note this function does not test number of neighbours – use `check_connection_n` for this.
    ! Please note this function does not test if edges move in two or three dimensions – use `check_single_edge_is_2D` for this.

    Args:
        - coord: (x, y, z) coordinates for the node of interest
        - connected_coords: a variable-length list of (x, y, z) coordinates for neighbouring nodes

    Returns:
        - bool: True if edges emanating from node flow in valid directions, else False.
    """

    # In TQEC, 3-way connections are possible if node and targets are co-planar

    # Calculate normalised displacements
    normalised_coords = [
        [(1 if i != 0 else 0) * (-1 if i < 0 else 1) for i in coord]
        for coord in connected_coords
    ]
    displacements = [(np.array(coord) - np.array(v)) for v in normalised_coords]

    # Filter element sum of displacements non zero items
    not_zeros = list(filter(lambda x: x != 0, np.sum(displacements, axis=0)))

    # Fail if there is more than one
    if len(not_zeros) > 1:
        return False

    # Pass otherwise
    return True


def check_valid_four_way(coord: tuple, connected_coords: list[tuple]):
    """
    Checks that the edges attached to a given node move in valid directions.

    ! Please note this function does not test number of neighbours – use `check_connection_n` for this.
    ! Please note this function does not test if edges move in two or three dimensions – use `check_single_edge_is_2D` for this.

    Args:
        - coord: (x, y, z) coordinates for the node of interest
        - connected_coords: a variable-length list of (x, y, z) coordinates for neighbouring nodes

    Returns:
        - bool: True if edges emanating from node flow in valid directions, else False.
    """

    # In TQEC, 4-way connections are possible if node and targets are co-planar

    # Calculate normalised displacements
    normalised_coords = [
        [(1 if i != 0 else 0) * (-1 if i < 0 else 1) for i in coord]
        for coord in connected_coords
    ]
    displacements = [(np.array(coord) - np.array(v)) for v in normalised_coords]

    # Fail if displacements do not cancel out
    if sum(np.array(sum(displacements))) != 0:
        return False

    # Pass otherwise
    return True
