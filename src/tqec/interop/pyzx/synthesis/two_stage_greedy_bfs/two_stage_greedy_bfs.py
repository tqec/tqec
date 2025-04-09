import random
import networkx as nx
from collections import deque
from typing import Tuple, List, Optional, Dict, Any

from tqec.interop.pyzx.synthesis.two_stage_greedy_bfs.utils.utils import (
    zx_types_validity_checks,
    get_type_family,
    check_for_exits,
    generate_tentative_target_positions,
)
from tqec.interop.pyzx.synthesis.two_stage_greedy_bfs.utils.classes import Path
from tqec.interop.pyzx.synthesis.two_stage_greedy_bfs.utils.pathfinder import (
    run_bfs_for_all_potential_target_nodes,
    obstacle_coords_from_preexistent_structure,
)
from tqec.interop.pyzx.synthesis.two_stage_greedy_bfs.grapher.grapher import (
    visualise_3d_graph,
    make_graph_from_edge_paths,
)


def _get_node_degree(graph: nx.Graph, node: int) -> int | float:
    degree = graph.degree(node)
    if isinstance(degree, int):
        return degree
    elif hasattr(degree, "__getitem__"):
        return degree[node]
    else:
        print(f"Warning: Unexpected degree type: {type(degree)}")
        return 0


def prepare_graph(graph: Dict[str, List[Any]]) -> nx.Graph:
    # PREPARE EMPTY NETWORKX GRAPH
    nx_graph = nx.Graph()

    # GET NODES AND EDGES FROM INCOMING ZX GRAPH
    nodes_data: List[Tuple[int, str]] = graph.get("nodes", [])
    edges_data: List[Tuple[Tuple[int, int], str]] = graph.get("edges", [])

    # ADD NODES TO NETWORKX GRAPH
    for node_id, node_type in nodes_data:
        nx_graph.add_node(
            node_id,
            type=node_type,
            type_family=get_type_family(node_type),
            kind=None,
            pos=None,
        )

    # ADD EDGES TO NETWORKX GRAPH
    for (u, v), edge_type in edges_data:
        nx_graph.add_edge(u, v, type=edge_type)

    # IDENTIFY THE NODES WITH MORE THAN 4 CONNECTIONS
    all_nodes = list(nx_graph.nodes())
    high_degree_nodes = [
        node for node in all_nodes if _get_node_degree(nx_graph, node) > 4
    ]

    # BREAK ANY NODES WITH MORE THAN 4 CONNECTIONS
    if high_degree_nodes:
        # Determine max degree
        max_node_id = max(nx_graph.nodes) if nx_graph.nodes else 0

        # Loop over max nodes and break as appropriate
        i = 0
        while i < 100:
            # List of high degree nodes
            all_nodes_loop = list(nx_graph.nodes())
            high_degree_nodes = [
                node for node in all_nodes_loop if _get_node_degree(nx_graph, node) > 4
            ]

            # Exit loop when no nodes with more than 4 edges
            if not high_degree_nodes:
                break

            # Pick a high degree node
            node_to_sanitise = random.choice(high_degree_nodes)
            original_node_type = nx_graph.nodes[node_to_sanitise]["type"]

            # Add a twin
            max_node_id += 1
            twin_node_id = max_node_id
            nx_graph.add_node(
                twin_node_id,
                type=original_node_type,
                type_family=get_type_family(original_node_type),
                kind=None,
                pos=None,
            )
            nx_graph.add_edge(node_to_sanitise, twin_node_id, type="SIMPLE")

            # Distributed edges across twins
            neighbors = list(nx_graph.neighbors(node_to_sanitise))
            neighbors = [n for n in neighbors if n != twin_node_id]

            degree_to_move = _get_node_degree(nx_graph, node_to_sanitise) // 2

            moved_count = 0
            random.shuffle(neighbors)

            for neighbor in neighbors:
                if (
                    moved_count >= degree_to_move
                    or _get_node_degree(nx_graph, node_to_sanitise) <= 4
                ):
                    break
                if nx_graph.has_edge(
                    node_to_sanitise, neighbor
                ) and not nx_graph.has_edge(twin_node_id, neighbor):
                    edge_data = nx_graph.get_edge_data(node_to_sanitise, neighbor)
                    edge_type = edge_data.get("type", None)
                    nx_graph.add_edge(twin_node_id, neighbor, type=edge_type)
                    nx_graph.remove_edge(node_to_sanitise, neighbor)
                    moved_count += 1

    # RETURN THE NETWORKX GRAPH
    return nx_graph


def choose_kind(
    tentative_position: Tuple[int, int, int],
    possible_kinds: Optional[List[str]],
    occupied_coords: List[Tuple[int, int, int]],
    all_beams: List[List[Tuple[int, int, int]]],
) -> Tuple[Optional[str], int, List[Tuple[int, int, int]]]:
    # HELPER VARIABLES
    most_exits = 0
    winner_kind: Optional[str] = None
    winner_idx: Optional[int] = None
    beams: List[List[Tuple[int, int, int]]] = []

    # LOOP OVER POSSIBLE KINDS FOR CUBE, IF ANY
    if possible_kinds:
        # Check if cube's exits are unobstructed
        for i, kind in enumerate(possible_kinds):
            unobstructed_exits_n, node_beams = check_for_exits(
                tentative_position, kind, occupied_coords, all_beams
            )
            print("===> result of check for exits: ", unobstructed_exits_n, node_beams)

            # Append cube's beams to global beams object
            beams.append(node_beams)

            # Choose kind with most unobstructed exits
            if unobstructed_exits_n > most_exits:
                most_exits = unobstructed_exits_n
                winner_kind = kind
                winner_idx = i

        # Return selected kind
        if winner_idx is not None:
            return winner_kind, most_exits, beams[winner_idx]

    # NONE/EMPTY RETURN IN THE EVENT OF A FAILURE
    return None, 0, []


def find_start_node_id(nx_graph: nx.Graph) -> Optional[int]:
    # TERMINATE IF THERE ARE NO NODES
    if not nx_graph.nodes:
        return None

    # LOOP OVER NODES FINDING NODES WITH HIGHEST DEGREE
    max_degree = -1
    central_nodes: List[int] = []

    node_degrees = nx_graph.degree()
    if isinstance(node_degrees, int):
        print(
            "Warning: nx_graph.degree() returned an integer. Cannot determine start node."
        )
        return None  # Cannot iterate, return None
    else:
        for node, degree in node_degrees:
            if degree > max_degree:
                max_degree = degree
                central_nodes = [node]
            elif degree == max_degree:
                central_nodes.append(node)

    # PICK A HIGHEST DEGREE NODE, RANDOMLY BUT FAVOURING LOWER NODES
    if central_nodes:
        start_node: Optional[int] = random.choice(central_nodes)
    else:
        start_node: Optional[int] = None

    # RETURN START NODE
    return start_node


def run_pathfinder(
    previous_node_info,
    next_neigh_zx_type,
    initial_step,
    occupied_coords,
    target_node_info=[],
):
    # ARRAYS TO HOLD TEMPORARY PATHS
    path = []
    valid_paths = []
    clean_paths = []

    # STEP, START, & TARGET COORDS
    step = initial_step
    start_coords, _ = previous_node_info

    target_coords = None
    target_type = None
    if target_node_info:
        target_coords, target_type = target_node_info

    # COPY OCCUPIED COORDS TO AVOID OVERWRITES BY EXTERNAL FUNCTIONS
    occupied_coords_copy = occupied_coords[:]
    if start_coords in occupied_coords_copy:
        occupied_coords_copy.remove(start_coords)
    if target_coords:
        occupied_coords_copy.remove(target_coords)

    # FIND VIABLE PATHS
    # One step at a time, call separate path finding (in a 4D space) BFS algorithm
    while step <= 18:
        # Generate tentative positions for current step or use target node
        if target_node_info:
            tentative_positions = [target_coords]
        else:
            tentative_positions = generate_tentative_target_positions(
                start_coords,
                step,
                occupied_coords,  # Real occupied coords: position cannot overlap start node
            )

        # Try finding path to each tentative positions
        for position in tentative_positions:
            path_found, best_path_length, best_path, all_paths_from_round = (
                run_bfs_for_all_potential_target_nodes(
                    previous_node_info,
                    next_neigh_zx_type,
                    step,
                    attempts_per_distance=1,
                    occupied_coords=occupied_coords_copy,  # Copy occupied coords: function uses source_coords differently
                    overwrite_target_node=[
                        position,
                        target_type,
                    ],
                )
            )

            # Append any found paths to valid_paths
            if path_found:
                valid_paths.append(all_paths_from_round)

        # Break if valid paths generated at step

        if valid_paths:
            break

        # Increase distance if no valid paths found at current step
        step += 3

    # REMOVE PATHS THAT INTERSECT WITH EXISTING CUBES/PIPES
    if target_node_info:
        if valid_paths and valid_paths[0]:
            clean_path = valid_paths[0][0]
            if occupied_coords_copy:
                for node in clean_path:
                    if (
                        node[0] in occupied_coords_copy
                    ):  # Copy occupied coords: path *will* contain source
                        return []
            # Return list with single clean path
            return [clean_path]
        else:
            return []

    else:
        if valid_paths:
            for all_paths in valid_paths:
                remove_flag = False
                for path in all_paths:
                    if occupied_coords_copy:
                        for node in path:
                            if (
                                node[0] in occupied_coords_copy
                            ):  # Copy occupied coords: path *will* contain source
                                remove_flag = True
                if not remove_flag:
                    clean_paths.append(path)

    # RETURN CLEAN PATHS OR EMPTY LIST IF NO VIABLE PATHS FOUND
    return clean_paths


def place_next_block(
    source_node_id: int,
    neigh_node_id: int,
    nx_graph: nx.Graph,
    occupied_coords: List[Tuple[int, int, int]],
    all_beams: List[List[Tuple[int, int, int]]],
    edge_paths: dict,
    step: int = 3,
    stage: float = 0.5,
) -> Tuple[List[Tuple[int, int, int]], List[List[Tuple[int, int, int]]], dict, bool]:
    # EXTRACT STANDARD INFO APPLICABLE TO ALL NODES
    # Previous node data
    source_pos: Optional[Tuple[int, int, int]] = nx_graph.nodes[source_node_id].get(
        "pos"
    )
    source_kind: Optional[str] = nx_graph.nodes[source_node_id].get("kind")

    if source_pos is None or source_kind is None:
        return occupied_coords, all_beams, edge_paths, False
    source_node = (source_pos, source_kind)

    # Current node data
    next_neigh_node_data = nx_graph.nodes[neigh_node_id]
    next_neigh_zx_type: Optional[List[str]] = next_neigh_node_data.get("type")
    next_neigh_edge_n = int(_get_node_degree(nx_graph, neigh_node_id))
    next_neigh_pos: Optional[Tuple[int, int, int]] = nx_graph.nodes[neigh_node_id].get(
        "pos"
    )

    # DEAL WITH CASES WHERE NEW NODE NEEDS TO BE ADDED TO GRID
    if next_neigh_pos is None:
        print(
            f"\nFinding path: node {source_node_id} @ {source_node} <-> node {neigh_node_id} @ {next_neigh_pos} (ZX type: {next_neigh_zx_type})"
        )
        print("Several attempts will be made. Algorithm keeps best.")

        # Remove source coordinate from occupied coords
        occupied_coords_redux = occupied_coords[:]
        if source_pos in occupied_coords_redux:
            occupied_coords_redux.remove(source_pos)

        # Get clean candidate paths
        clean_paths = run_pathfinder(
            source_node,
            next_neigh_zx_type,
            step,
            occupied_coords_redux if occupied_coords else [],
        )
        print(f"- {len(clean_paths)} paths found. Performing health-checks on all.")

        # Assemble a preliminary dictionary of viable paths
        viable_paths = []
        for clean_path in clean_paths:
            # Get all theoretically possible paths
            target_coords, target_kind = clean_path[-1]
            target_unobstructed_exits_n, target_node_beams = check_for_exits(
                target_coords, target_kind, occupied_coords_redux, all_beams
            )

            # Reset # of unobstructed exits and node beams if node is a boundary
            if next_neigh_zx_type == "O":
                target_unobstructed_exits_n, target_node_beams = (6, [])

            # Check node has min # unobstructed exits than needed
            if target_unobstructed_exits_n >= next_neigh_edge_n:
                coords_in_path = [entry[0] for entry in clean_path]
                beams_broken_by_path = 0
                for beam in all_beams:
                    for coord in beam:
                        if coord in coords_in_path:
                            beams_broken_by_path += 1

                # Write edge to patd_data if node clears checks
                all_nodes_in_path = [entry for entry in clean_path]
                if next_neigh_zx_type == "O":
                    target_kind = "ooo"
                    all_nodes_in_path[-1][1] = target_kind

                path_data = {
                    "target_pos": target_coords,
                    "target_kind": target_kind,
                    "target_beams": target_node_beams,
                    "coords_in_path": coords_in_path,
                    "all_nodes_in_path": [entry for entry in clean_path],
                    "beams_broken_by_path": beams_broken_by_path,
                    "len_of_path": len(clean_path),
                    "target_unobstructed_exits_n": target_unobstructed_exits_n,
                }

                viable_paths.append(Path(**path_data))

        print(
            f"- A total of {len(viable_paths)} paths survived health checks. Choosing a winner path."
        )

        winner_path: Optional[Path] = None
        if viable_paths:
            winner_path = max(viable_paths, key=lambda path: path.weighed_value(stage))

        # Rewrite current node with data of winner candidate
        if winner_path:
            # Update node information
            nx_graph.nodes[neigh_node_id]["pos"] = winner_path.target_pos
            nx_graph.nodes[neigh_node_id]["kind"] = winner_path.target_kind

            # Update edge_path dictionary
            edge = tuple(sorted((source_node_id, neigh_node_id)))
            edge_type = nx_graph.get_edge_data(source_node_id, neigh_node_id).get(
                "type", "SIMPLE"
            )  # Default to "SIMPLE" if type is not found
            edge_paths[edge] = {
                "path_coordinates": winner_path.coords_in_path,
                "path_nodes": winner_path.all_nodes_in_path,
                "edge_type": edge_type,
            }

            # Add path to position to list of graphs' occupied positions
            full_coords_to_add = obstacle_coords_from_preexistent_structure(
                winner_path.all_nodes_in_path
            )
            occupied_coords.extend(full_coords_to_add)

            # Add beams of winner's target node to list of graphs' all_beams
            all_beams.append(winner_path.target_beams)

            # Return updated occupied_coords and all_beams, with success code
            return occupied_coords, all_beams, edge_paths, True

        # Handle cases where no winner is found
        if not winner_path:
            # Explicit warning
            print(f"Could not find path to node {neigh_node_id} within step {step}.")

            # Fill edge_path with error (allows process to move on but error is easy to spot)
            edge = tuple(sorted((source_node_id, neigh_node_id)))
            edge_paths[edge] = {
                "path_coordinates": "error",
                "path_nodes": "error",
                "edge_type": "error",
            }

            # Return unchanged occupied_coords and all_beams, with failure boolean
            return occupied_coords, all_beams, edge_paths, False

    # DEAL WITH CASES WHERE BOTH NODES ARE ALREADY IN GRID
    if next_neigh_pos is not None:
        print(f"Finding path between nodes {source_node_id} and {neigh_node_id}")

        # Get target kind
        target_kind: Optional[str] = nx_graph.nodes[neigh_node_id].get("kind")

        # Remove source coordinate from occupied coords
        occupied_coords_redux = occupied_coords[:]
        if source_pos in occupied_coords_redux:
            occupied_coords_redux.remove(source_pos)
        if next_neigh_pos in occupied_coords_redux:
            occupied_coords_redux.remove(next_neigh_pos)

        # Find paths between existing nodes
        clean_paths = run_pathfinder(
            source_node,
            next_neigh_zx_type,
            step,
            occupied_coords_redux if occupied_coords else [],
            target_node_info=[next_neigh_pos, target_kind],
        )

        # If there is a path
        if clean_paths:
            for clean_path in clean_paths:
                coords_in_path = [entry[0] for entry in clean_path]
                return occupied_coords, all_beams, edge_paths, True

            for clean_path in clean_paths:
                coords_in_path = [entry[0] for entry in clean_path]

                # Update edge_path dictionary
                edge = tuple(sorted((source_node_id, neigh_node_id)))
                edge_type = nx_graph.get_edge_data(source_node_id, neigh_node_id).get(
                    "type", "SIMPLE"
                )  # Default to "SIMPLE" if type is not found
                edge_paths[edge] = {
                    "path_coordinates": coords_in_path,
                    "path_nodes": clean_path,
                    "edge_type": edge_type,
                }

                # Update occupied coords
                full_coords_to_add = obstacle_coords_from_preexistent_structure(
                    clean_path
                )
                occupied_coords.extend(full_coords_to_add)

                # Update all_beams
                # No need to update all_beams. No new nodes. No new beams.
                # No need to establish how many beams path breaks: no selection between alternative paths possible for a single path.

                # Return updated occupied_coords and all_beams, with success code
                return occupied_coords, all_beams, edge_paths, True
        else:
            # No path found between existing nodes
            print(
                f"Could not find path between already placed nodes {source_node_id} and {neigh_node_id}."
            )
            edge = tuple(sorted((source_node_id, neigh_node_id)))
            edge_paths[edge] = {
                "path_coordinates": "error",
                "path_nodes": "error",
                "edge_type": "error",
            }

            # Return unchanged occupied_coords and all_beams, with failure boolean
            return occupied_coords, all_beams, edge_paths, False

    # FAIL SAFE RETURN TO AVOID TYPE ERRORS
    return occupied_coords, all_beams, edge_paths, False


def second_pass(
    nx_graph: nx.Graph,
    occupied_coords: List[Tuple[int, int, int]],
    all_beams: List[List[Tuple[int, int, int]]],
    edge_paths: dict,
    c: int,
) -> Tuple[dict, int]:
    # Update user
    print("\nStarting second pass to connect already placed nodes.")

    # BASE ALL OPERATIONS ON EDGES FROM GRAPH
    for u, v, data in nx_graph.edges(data=True):
        # Ensure occupied coords do not have duplicates
        occupied_coords = list(set(occupied_coords))

        # Get source and target node for specific edge
        u_pos = nx_graph.nodes[u].get("pos")
        v_pos = nx_graph.nodes[v].get("pos")

        # Process only if both nodes have been placed on grid already
        if u_pos is not None and v_pos is not None:
            # Format adjustments to match existing operations
            u_kind = nx_graph.nodes[u].get("kind")
            v_zx_type = nx_graph.nodes[v].get("type")
            u_node = (u_pos, u_kind)
            edge = tuple(sorted((u, v)))

            # Call pathfinder on any graph edge that does not have an entry in edge_paths
            if edge not in edge_paths:
                print(
                    f"\nFinding path between existing nodes: {u}@{u_pos} - {v}@{v_pos}"
                )

                # Call pathfinder using optional parameters to tell the pathfinding algorithm
                # to work in pure pathfinding (rather than path creation) mode
                clean_paths = run_pathfinder(
                    u_node,
                    v_zx_type,
                    3,
                    occupied_coords[:],
                    target_node_info=[v_pos, nx_graph.nodes[v].get("kind")],
                )

                # Write to edge_paths if an edge is found
                if clean_paths:
                    print(f"Found {len(clean_paths)} paths for edge ({u}, {v}).")
                    coords_in_path = [
                        entry[0] for entry in clean_paths[0]
                    ]  # Take the first path
                    edge_type = data.get("type", "SIMPLE")
                    edge_paths[edge] = {
                        "path_coordinates": coords_in_path,
                        "path_nodes": clean_paths[0],
                        "edge_type": edge_type,
                    }

                    # Create new graph from updated edge_paths
                    new_nx_graph = make_graph_from_edge_paths(edge_paths)

                    # VISUALISE NEW EDGE
                    visualise_3d_graph(new_nx_graph)
                    visualise_3d_graph(
                        new_nx_graph, save_to_file=True, filename=f"steane{c:03d}"
                    )

                    # Update visualiser counter
                    c += 1

                # Write an error to edge_paths if edge not found
                else:
                    print(
                        f"Could not find path for edge ({u}, {v}) between placed nodes."
                    )
                    edge_paths[edge] = {
                        "path_coordinates": "error",
                        "path_nodes": "error",
                        "edge_type": "error",
                    }

    # RETURN EDGE PATHS FOR FINAL CONSUMPTION
    return edge_paths, c


def main(graph: Dict[str, List[Any]]) -> Tuple[nx.Graph, dict, nx.Graph]:
    # KEY VARIABLES
    # Take a ZX graph and prepare a fresh 3D graph with positions set to None
    nx_graph = prepare_graph(graph)

    # Arrays/dicts to track coordinates
    occupied_coords: List[Tuple[int, int, int]] = []
    all_beams: List[List[Tuple[int, int, int]]] = []
    edge_paths: dict = {}

    # VALIDITY CHECKS
    if not zx_types_validity_checks(graph):
        print("Graph validity checks failed. Aborting.")
        return (
            nx_graph,
            edge_paths,
            nx.Graph(),
        )  # Return an empty graph or handle as needed

    # BFS management
    start_node: Optional[int] = find_start_node_id(nx_graph)
    queue: deque = deque([start_node])
    visited: set = {start_node}

    # SPECIAL PROCESS FOR CENTRAL NODE
    # Terminate if there is no start node
    if start_node is None:
        print("Graph has no nodes.")
        return nx_graph, edge_paths, nx.Graph()

    # Place start node at origin
    else:
        # Get kind from type family
        randomly_chosen_kind: Optional[str] = None
        possible_kinds: Optional[List[str]] = nx_graph.nodes[start_node].get(
            "type_family"
        )
        randomly_chosen_kind = random.choice(possible_kinds) if possible_kinds else None

        # Write info of node
        nx_graph.nodes[start_node]["pos"] = (0, 0, 0)
        nx_graph.nodes[start_node]["kind"] = randomly_chosen_kind

        # Update occupied_coords and all_beams with node's position & beams
        occupied_coords.append((0, 0, 0))
        _, start_node_beams = check_for_exits(
            (0, 0, 0), randomly_chosen_kind, occupied_coords, all_beams
        )
        all_beams.append(start_node_beams)

    # LOOP FOR ALL OTHER NODES
    c = 0  # Visualiser counter (needed to save snapshots to file)
    while queue:
        # Get current parent node
        current_parent_node: int = queue.popleft()

        # Iterate over neighbours of current parent node
        for neigh_node_id in nx_graph.neighbors(current_parent_node):
            # Queue and add to visited set if BFS just arrived at node
            if neigh_node_id not in visited:
                visited.add(neigh_node_id)
                queue.append(neigh_node_id)

                # Ensure occupied_coords has unique entries each run
                occupied_coords = list(set(occupied_coords))

                # Try to place blocks as close to one another as as possible
                step = 3
                while step <= 18:
                    occupied_coords, all_beams, edge_paths, successful_placement = (
                        place_next_block(
                            current_parent_node,
                            neigh_node_id,
                            nx_graph,
                            occupied_coords,
                            all_beams,
                            edge_paths,
                            step=step,
                        )
                    )

                    # For visualisation purposes, on each step,
                    # create a new graph from edge_paths
                    if edge_paths:
                        if c < int(len(edge_paths)):
                            if list(edge_paths.values())[-1]["path_nodes"] != "error":
                                # Create graph from existing edges
                                new_nx_graph = make_graph_from_edge_paths(edge_paths)

                                # Create visualisation
                                visualise_3d_graph(new_nx_graph)
                                visualise_3d_graph(
                                    new_nx_graph,
                                    save_to_file=True,
                                    filename=f"steane{c:03d}",
                                )

                                c = len(edge_paths)

                    # Move to next is there is a successful placement
                    if successful_placement:
                        break

                    # Increase distance between nodes if placement not possible
                    step += 3

    # SINCE IT WAS USED EXTENSIVELY DURING LOOP
    # ENSURE OCCUPIED COORDS ARE UNIQUE
    occupied_coords = list(set(occupied_coords))

    # RUN OVER GRAPH AGAIN IN CASE SOME EDGES WHERE NOT BUILT AS A RESULT OF MAIN LOOP
    edge_paths, c = second_pass(nx_graph, occupied_coords, all_beams, edge_paths, c)

    # CREATE A NEW GRAPH FROM FINAL EDGE PATHS RETURNS FROM ALL THE BOVE
    new_nx_graph = make_graph_from_edge_paths(edge_paths)

    # VISUALISE FINAL LATTICE SURGERY
    visualise_3d_graph(new_nx_graph)
    visualise_3d_graph(new_nx_graph, save_to_file=True, filename=f"steane{c:03d}")

    # CREATE A GIF FROM THE VISUALISATIONS
    # Uncomment only if imageio library is installed on environment
    # create_animation(
    # "./src/tqec/interop/pyzx/synthesis/two_stage_greedy_bfs/grapher/plots/",
    # filename_prefix="steane_animation",
    # restart_delay=5000,
    # duration=2500,
    # )

    # RETURN THE GRAPHS AND EDGE PATHS FOR ANY SUBSEQUENT USE
    return nx_graph, edge_paths, new_nx_graph


# EXAMPLE USAGE
# THE CODE BELOW CAN BE USED TO TEST THE ALGORITHM WITH A 7 QUBIT STEANE CODE
if __name__ == "__main__":
    steane: Dict[str, List[Any]] = {
        "nodes": [
            [1, "X"],
            [2, "Z"],
            [3, "Z"],
            [4, "Z"],
            [5, "X"],
            [6, "X"],
            [7, "X"],
            [8, "O"],
            [9, "O"],
            [10, "O"],
            [11, "O"],
            [12, "O"],
            [13, "O"],
            [14, "O"],
        ],
        "edges": [
            ((1, 2), "SIMPLE"),
            ((1, 3), "SIMPLE"),
            ((1, 4), "SIMPLE"),
            ((5, 2), "SIMPLE"),
            ((5, 3), "SIMPLE"),
            ((6, 2), "SIMPLE"),
            ((6, 4), "SIMPLE"),
            ((7, 3), "SIMPLE"),
            ((7, 4), "SIMPLE"),
            ((8, 1), "SIMPLE"),
            ((9, 5), "SIMPLE"),
            ((10, 6), "SIMPLE"),
            ((11, 7), "SIMPLE"),
            ((2, 12), "SIMPLE"),
            ((3, 13), "SIMPLE"),
            ((4, 14), "SIMPLE"),
        ],
    }

    # CALL TO ALGORITHM
    nx_graph_3d, edge_paths, new_nx_graph = main(steane)

    # PRINTOUT OF RESULTS
    print("\nNodes:")
    for node_id, data in nx_graph_3d.nodes(data=True):
        print(f"  Node ID: {node_id}, Attributes: {data}")

    print("\nEdges:")
    for u, v, data in nx_graph_3d.edges(data=True):
        print(f" Edge: ({u}, {v}), Attributes: {data}")

    print("\nEdge paths:")
    for key, edge_path in edge_paths.items():
        print(f"  {key}: {edge_path['path_nodes']}")
