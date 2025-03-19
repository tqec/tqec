"""Extracts information from a PyZX graph into a
single easy-to-use mega-dictionary that other functions / methods can use.

Intended as a common point of departure for 2D PyZX graph -> TQEC journey.

"""

import copy


def extract_info_from_graph(g):
    """
    Extracts spatial information from a PyZX graph.

    Args:
        - g: a PyZX graph.

    Returns:
        - reformatted_graph: a dictionary with the information from g, formatted to match standard 3D syntax.
    """

    # CREATE NEW DICTIONARY (FOR BETTER ORGANISATION)
    graph_dict = {"meta": {}, "nodes": {}, "edges": {}}

    try:
        graph_dict["meta"]["scalar"] = g.to_dict(include_scalar=True)["scalar"]

        for v in g.vertices():
            graph_dict["nodes"][v] = {
                "pos": [g.row(v), g.qubit(v), 0],
                "rot": [0, 0, 0],
                "scale": [0, 0, 0],
                "t": g.type(v).name,
                "phase": str(g.phase(v)),
                "degree": g.vertex_degree(v),
                "connections": list(g.neighbors(v)),
            }

        c = 0
        for e in g.edges():
            graph_dict["edges"][f"e{c}"] = {
                "t": g.edge_type(e).name,
                "src": e[0],
                "tgt": e[1],
            }
            c += 1
    except Exception as e:
        print(f"Error extracting info from the PyZX graph: {e}")

    # RETURN NEW DICTIONARY
    reformatted_graph = copy.deepcopy(graph_dict)
    return reformatted_graph
