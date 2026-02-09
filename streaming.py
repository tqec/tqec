import random
from time import time

import stim

from tqec import BlockGraph
from tqec.circuit.qubit import GridQubit
from tqec.circuit.qubit_map import QubitMap
from tqec.compile.compile import compile_block_graph
from tqec.utils import TQECError
from tqec.utils.position import Position3D


def _generate_qubit_map(x, y, k):
    d = 2 * k + 1
    a = 2 * d

    xa = a * x + 2 * (x - 1) + 1
    ya = a * y + 2 * (y - 1) + 1

    qubits: dict[int, GridQubit] = {}

    i = 0
    for b in range(xa):
        for c in range(ya):
            if (b + c) % 2 == 1:
                continue
            qubits[i] = GridQubit(b, c)
            i += 1

    qm = QubitMap(qubits)

    return qm


def _random_block_graph(nx: int, ny: int, t: int) -> BlockGraph:
    graph = BlockGraph()

    cd = ["ZXX", "ZXZ"]

    r = random.Random(100)

    # Create nxn grid at each time slice
    for x in range(nx):
        for y in range(ny):
            graph.add_cube(Position3D(x, y, 0), r.choice(cd))

    # Add spatial connections within the first layer
    for x in range(nx):
        for y in range(ny):
            try:
                if x < nx - 1:
                    graph.add_pipe(Position3D(x, y, 0), Position3D(x + 1, y, 0))
            except TQECError:
                pass

            try:
                if y < ny - 1:
                    graph.add_pipe(Position3D(x, y, 0), Position3D(x, y + 1, 0))
            except TQECError:
                pass

    # Add temporal layers and connections
    for i in range(1, t):
        # Add all cubes in the nxn grid at time slice i
        for x in range(nx):
            for y in range(ny):
                graph.add_cube(Position3D(x, y, i), r.choice(cd))
                # Add temporal pipe from previous time slice
                try:
                    graph.add_pipe(Position3D(x, y, i - 1), Position3D(x, y, i))
                except TQECError:
                    pass

        # Add spatial connections within this layer
        if i != t - 1:
            for x in range(nx):
                for y in range(ny):
                    try:
                        if x < nx - 1:
                            graph.add_pipe(Position3D(x, y, i), Position3D(x + 1, y, i))
                    except TQECError:
                        pass

                    try:
                        if y < ny - 1:
                            graph.add_pipe(Position3D(x, y, i), Position3D(x, y + 1, i))
                    except TQECError:
                        pass

    return graph


def benchmark_stream(nx: int, ny: int, t: int, k: int, compare_to_unstreamed: bool = False) -> None:
    """Benchmark streaming generation of quantum circuits for a compiled block graph.

    Generates a block graph, compiles it into a layer tree, and produces circuit
    instructions via streaming. Optionally compares streamed results with unstreamed
    generation. Logs timing metrics for performance analysis.

    NOTE: The qubit map used for streaming is different from the one used for unstreamed,
    even though the resulting circuit is functionally the same. To prove the unstreamed
    and streamed circuits are exactly the same, we need to use the same qubit map for both.
    This means piping the qubit map from the unstreamed generation into the streamed generation.

    Args:
        nx: Number of blocks along the x-axis in the block graph.
        ny: Number of blocks along the y-axis in the block graph.
        t: Time parameter for generating the block graph.
        k: Number of layers to use for circuit generation in the layer tree.
        compare_to_unstreamed: Whether to compare the streamed circuit with an
            unstreamed circuit. Defaults to False.

    """
    start = time()
    block_graph = _random_block_graph(nx, ny, t)
    compiled_graph = compile_block_graph(block_graph, observables="auto")
    lt = compiled_graph.to_layer_tree()
    end = time()
    print(f"Layer tree generation time (s): {end - start}\n")

    circuit = None
    if compare_to_unstreamed:
        lt2 = compiled_graph.to_layer_tree()  # a copy is needed here

        start = time()
        circuit = lt2.generate_circuit(k)
        end = time()
        print(f"Unstreamed circuit generation time (s): {end - start}\n")

        magic_qm = lt2._get_global_qubit_map(k)
    else:
        magic_qm = _generate_qubit_map(
            nx, ny, k
        )  # This qubit map is not tight on the qubits needed.

    start = time()
    citer = lt.generate_circuit_stream(k, magic_qm)
    end = time()
    print(f"Initial stream generation time (s): {end - start}\n")

    start = time()

    last = time()
    master_circuit = stim.Circuit() if compare_to_unstreamed else None
    with open("master_circuit.txt", "w+") as f:
        print("Index, Time Taken (s), Circuit Snippet")
        i = 0
        for circ in citer:
            print(f"{i}, {time() - last}, " + circ.__str__()[:20].replace("\n", " "))
            last = time()
            i += 1
            f.write(str(circ) + "\n")
            if compare_to_unstreamed:
                assert master_circuit is not None
                master_circuit += circ

    end = time()
    print(f"Total streamed circuit generation time (s): {end - start}\n")

    if compare_to_unstreamed:
        print("Comparing streamed vs unstreamed circuits...")
        same = master_circuit == circuit
        if same:
            print("Circuits are the same!")
        else:
            print("Circuits are different!")
        assert same


if __name__ == "__main__":
    nx = 3
    ny = 3
    t = 5
    k = 1

    benchmark_stream(nx, ny, t, k, compare_to_unstreamed=True)
