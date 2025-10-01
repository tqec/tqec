Build Computations
==================

In :code:`tqec`, a logical computation is represented as a :code:`BlockGraph`. There are several ways to build it:

1. Build the structure interactively with `SketchUp <https://www.sketchup.com/app>`_, export and convert it to a :code:`BlockGraph`.
2. Build a :code:`BlockGraph` programmatically with :code:`add_cube` and :code:`add_pipe` methods.
3. Build a :code:`pyzx.GraphS` ZX graph representation of the computation and synthesize it to a :code:`BlockGraph`.

In this notebook, we will guide you through all the methods.

1. Use SketchUp
----------------

`SketchUp <https://www.sketchup.com/app>`_ is a 3D modeling tool widely used in QEC community to build the spacetime diagram for logical computations.
Its user-friendly interface allows you to easily create and manipulate the computation blocks.

Once you make a Trimble account, you may freely use the web version of SketchUp to import a :code:`.skp` file and create a scene. However, unless you are on
a Windows machine, you must either activate a paid license or free trial to export a SketchUp :code:`.skp` file as a COLLADA :code:`.dae` file. On Windows, it suffices
to use the `freeware version SketchUp8 <https://google-sketchup.en.lo4d.com/download>`_.

Users that are not on Windows may fully use :code:`tqec` via the programmatic construction below. Please notify a developer if you are aware of a way to export a
SketchUp scene to a :code:`.dae` file on Mac OSX or Linux.

The workflow using SketchUp to build computations is as follows:

1. Open the `template file <https://github.com/tqec/tqec/blob/main/assets/template.skp>`_ in SketchUp.
2. Use the building blocks provided in the template file to build your computation. After you finish building, remove the template blocks from the scene.
3. Save and export the model to :code:`.dae` file format.
4. Import the computation into :code:`tqec` using the :code:`tqec.read_block_graph_from_dae_file` or :code:`BlockGraph.from_dae_file()` function.

2. Build :code:`BlockGraph` directly
------------------------------------

You can add blocks to a :code:`BlockGraph` by calling :code:`add_cube` and :code:`add_pipe`. Here we show how to build a logical CNOT directly with :code:`BlockGraph`.

.. jupyter-execute::

    from tqec import BlockGraph
    from tqec.utils.position import Position3D

    g = BlockGraph("CNOT")
    cubes = [
        (Position3D(0, 0, 0), "P", "In_Control"),
        (Position3D(0, 0, 1), "ZXX", ""),
        (Position3D(0, 0, 2), "ZXZ", ""),
        (Position3D(0, 0, 3), "P", "Out_Control"),
        (Position3D(0, 1, 1), "ZXX", ""),
        (Position3D(0, 1, 2), "ZXZ", ""),
        (Position3D(1, 1, 0), "P", "In_Target"),
        (Position3D(1, 1, 1), "ZXZ", ""),
        (Position3D(1, 1, 2), "ZXZ", ""),
        (Position3D(1, 1, 3), "P", "Out_Target"),
    ]
    for pos, kind, label in cubes:
        g.add_cube(pos, kind, label)

    pipes = [(0, 1), (1, 2), (2, 3), (1, 4), (4, 5), (5, 8), (6, 7), (7, 8), (8, 9)]

    for p0, p1 in pipes:
        g.add_pipe(cubes[p0][0], cubes[p1][0])

    g.view_as_html()

3. :code:`pyzx.GraphS` and synthesis
------------------------------------

For large scale quantum computation, we might use :code:`pyzx` as a upstream compiler and take optimized ZX diagrams as inputs to :code:`tqec`. We need to synthesis the
reduced ZX diagram to valid :code:`BlockGraph` realization.

Currently, we only support very naive synthesis strategy that requires specifying positions of every vertex in the ZX diagram explicitly. Here we take logical
S gate teleportation for example to show how to take a :code:`pyzx` graph as input and synthesis it to a :code:`BlockGraph`.

.. jupyter-execute::

    from fractions import Fraction

    from pyzx import EdgeType, VertexType
    from pyzx.graph.graph_s import GraphS

    from tqec.interop import block_synthesis
    from tqec.utils.position import Position3D

    g_zx = GraphS()
    g_zx.add_vertices(5)
    g_zx.set_type(1, VertexType.Z)
    g_zx.set_type(3, VertexType.Z)
    g_zx.set_type(4, VertexType.Z)
    g_zx.set_phase(4, Fraction(1, 2))
    g_zx.add_edges([(0, 1), (1, 2), (1, 3), (3, 4)])
    g_zx.set_inputs((0,))
    g_zx.set_outputs((2,))

    positions = {
        0: Position3D(0, 0, 0),
        1: Position3D(0, 0, 1),
        2: Position3D(0, 0, 2),
        3: Position3D(1, 0, 1),
        4: Position3D(1, 0, 2),
    }

    g = block_synthesis(g_zx, positions=positions)
    g.view_as_html()
