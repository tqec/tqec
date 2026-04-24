BGRAPH Schema
========================

BGRAPH is a work-in-progress file format (`.bgraph`) that can be used to facilitate interoperability between external lattice surgery (LS) tools.

While only a preliminary minimum baseline in need of improvement, the current BGRAPH specification already enjoys the following advantages:

- Common format both `Topologiq <https://github.com/tqec/topologiq>`_ and `TopoLS <https://github.com/tqec/TopoLS>`_ can produce
- Human-readable (QASM-like) format that is easy to inspect
- Clear structure that allows parsing using
- Sufficiently complete as to enable read/write of any arbitrary blockgraph :code:`tqec` can currently handle.

We welcome proposals for improved specifications that expand upon these minimum advantages. In the ideal scenario, we foresee future versions of BGRAPH being flexible enough as to enable interoperability *at any stage* of the LS process, which the current version cannot yet do.

Schema
-------
A BGRAPH file can be conceived as a QASM-like representation of a lattice surgery.

Any BGRAPH file should be divided into four main sections:
- HEADER: The title of the document, with information about the source tool used to produce it.
- METADATA: A short section with meta information on top
- CUBES: A subsequent section with detailed information about the cubes in the blockgraph
- PIPES: A final section with detailed information about the cubes in the blockgraph.

An example BGRAPH file is available from :code:`tqec.assets`, `here <https://github.com/tqec/tqec/blob/main/assets/cnots.bgraph>`_.

Header
~~~~~~
Contains the file header.

The information in this section is for identification purposes and is not meant to be parsed.

.. admonition:: Example

    .. code-block:: text

        BLOCKGRAPH 0.1.0;

METADATA
~~~~~~~~
Contains the information needed to produce a blockgraph using the information available in other sections.

The information in this section is parseable, but the specific fields are optional:
- length of pipes used in the source tool: The length of the pipes between any two adjacent cubes (see note at the end of this section).
- name of the circuit: used to give the blockgraph a reference name.

Each METADATA item should be given as a CSV-separated pair. If a field is not included, TQEC will assign default values.

.. admonition:: Example

    .. code-block:: text

        METADATA: attr_name; value;
        source; name_of_tool_that_created_the_file;
        pipe_length; 2.0;
        circuit_name; CNOTs;

.. note::

    Fields in this section are optional. Note, in particular, that if `pipe_length` is not given, the TQEC parser will default to `pipe_length = 0.0`.

CUBES
~~~~~
Contains the information needed to translate each line of this section into a :code:`tqec` `cube <./terminology.rst>`.

The information in this section is meant to be parsed and must contain, at a minimum:
- index: the ID of the cube, ideally an integer but alphanumeric IDs also possible.
- position: The (x, y, z) position of the cube, a tuple of integers.
- kind: The kind of the cube, as a string (see `Terminology <https://tqec.github.io/tqec/user_guide/terminology.html>`_, as well as the note below).
- label (optional): An optional annotation that is typically used to denote when a cube is a PORT.

Each CUBE item should be given as a CSV-separated sequence.

.. admonition:: Example

    .. code-block:: text

        CUBES: index;x;y;z;kind;label;
        4;0;0;0;zxz;;
        3;3;0;0;xxz;;
        0;6;0;0;ooo;in_0;
        8;-6;0;0;ooo;out_0;


.. note::

    There is no fully-agreed denomination for open boundaries/ports or Y-cubes. For the time being, it is possible to use "ooo" or "P" for ports and "Y", "yi", "ym" to denote a Y-cube.

PIPES
~~~~~
Contains the information needed to translate each line of this section into a :code:`tqec` `pipe <./terminology.rst>`.

The information in this section is meant to be parsed and must contain, at a minimum:
- index: the ID of the cube, typically an integer.
- u: The ID of the cube at which the pipe starts (the source for the edge represented by the pipe).
- v: The ID of the cube at which the pipe ends (the target for the edge represented by the pipe).
- kind: The kind of the pipe (see `Terminology <https://tqec.github.io/tqec/user_guide/terminology.html>`_ for all possibilities.).

Each PIPE item should be given as a CSV-separated sequence.

.. admonition:: Example

    .. code-block:: text

        PIPES: src;tgt;kind;
        4;3;oxz;
        4;5;zxo;
        4;6;oxz;
        16;18;ozxh;

Parsing a BGRAPH
----------------

If you have a BGRAPH file, you can easily convert it into a blockgraph using :code:`tqec`'s :code:`tqec.computation.block_graph.from_bgraph`.

.. jupyter-execute::

    from tqec import BlockGraph

    filepath = "../assets/cnots.bgraph"
    graph = BlockGraph.from_bgraph(filepath)

You can then display and use the resulting blockgraph using other TQEC methods.

For instance, you can call :code:`BlockGraph.view_as_html` to visualize the blockgraph.

.. jupyter-execute::

    graph.view_as_html()

Additionally, you can attach the correlation surface to the model to visualize what the logical observable looks like:

.. jupyter-execute::

    correlation_surfaces = graph.find_correlation_surfaces()
    graph.view_as_html(
        pop_faces_at_directions=("-Y",),
        show_correlation_surface=correlation_surfaces[0],
    )

And, of course, you can follow the same instructions available in several gallery docs (for instance, this `Steane code example <https://tqec.github.io/tqec/pull/864/gallery/steane_encoding.html>`_) to produce circuits and simulate the blockgraph.


Producing a BGRAPH
------------------

It is also possible to produce a BGRAPH of any TQEC blockgraph.

In the example below, we print the BGRAPH string instead of saving it to file, but the same procedure can be used to save the string to a file with :code:`.bgraph` extension by removing :code:`save_to_file=False` or changing it to :code:`save_to_file=True`.

.. jupyter-execute::

    # Import example blockgraph from gallery
    from pathlib import Path
    from tqec.gallery import cnot
    from tqec.utils.enums import Basis

    block_graph = cnot(Basis.X)

    # Define path to output file
    path_to_output_file = Path("cnot.bgraph")

    # Write to BGRAPH
    bgraph_out_str = write_bgraph(
        graph,
        path_to_output_file,  # Required but used only if `save_to_file` is `True` or removed (defaults to `True`)
        graph_name="cnot",
        save_to_file=False,
    )

    # Inspect BGRAPH string
    print(bgraph_out_str)
