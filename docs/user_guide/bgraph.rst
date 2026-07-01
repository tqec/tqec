BGRAPH Schema
=============
BGRAPH is a work-in-progress file format (`.bgraph`) that can be used to facilitate interoperability between external lattice surgery (LS) tools.

While only a preliminary minimum baseline in need of improvement, the current BGRAPH specification already enjoys the following advantages:

- Common format that `Topologiq <https://github.com/tqec/topologiq>`_ and `TopoLS <https://github.com/tqec/TopoLS>`_ can produce.
- Human-readable (QASM-like) format that is easy to inspect.
- Clear structure that allows parsing using.
- Sufficiently complete as to enable read/write of any arbitrary block graph :code:`tqec` can currently handle.

We welcome proposals for improved specifications that expand upon these minimum advantages.
We foresee future versions of BGRAPH being flexible enough as to enable interoperability *at any stage* of the LS process, which the current version cannot yet do.

Schema
------
A BGRAPH file can be conceived as a QASM-like representation of a lattice surgery.

Any BGRAPH file should be divided into four main sections:

- ``Header``: the title of the document, with information about the source tool used to produce it.
- ``Metadata``: a short section with meta information on top.
- ``Cubes``: a subsequent section with detailed information about the cubes in the block graph.
- ``Pipes``: a final section with detailed information about the pipes in the block graph.

An example BGRAPH file is available from :code:`tqec.assets`.

Header
~~~~~~
Contains the file header.

The information in this section is for identification purposes and is not meant to be parsed.

.. admonition:: Example

    .. code-block:: text

        BLOCKGRAPH 0.1.0;

Metadata
~~~~~~~~
Contains the information needed to produce a block graph using the information available in the other sections.

The information in this section is parseable, but the specific fields are optional:

- ``source``: the tool used to create the BGRAPH.
- ``circuit_name``: used to give the block graph a reference name.
- ``pipe_length``: the length of the pipes between any two adjacent cubes (see note at the end of this section).

Each Metadata item should be given as a CSV-separated pair. If a field is not included, ``tqec`` will assign default values.

.. admonition:: Example

    .. code-block:: text

        METADATA: attr_name; value;
        source; name_of_tool_that_created_the_file;
        circuit_name; CNOTs;
        pipe_length; 2.0;

.. note::

    Fields in this section are optional. Note, in particular, that if `pipe_length` is not given, the ``tqec`` parser will default to `pipe_length = 0.0`.

Cubes
~~~~~
Contains the information needed to translate each line of this section into a :code:`tqec` :ref:`Cube <cube>`.

The information in this section is meant to be parsed and must contain, at a minimum:

- ``index``: the ID of the cube, ideally an integer but alphanumeric IDs also possible.
- ``x``, ``y``, ``z``: the position of the cube, a tuple of integers.
- ``kind``: the kind of the cube, as a string (see :ref:`Cube <cube>`, as well as the note below).

Optionally, it may also contain a ``label``, an annotation that is typically used to denote when a cube is a :ref:`Port <port>`.

Each Cube item should be given as a CSV-separated sequence.
All separating semicolons should be included even if the (optional) label field is blank.
This helps communicating explicitly to the parser that there is no label (for robustness, the parses *will* fail if an incorrect number of semi-colons is used).

.. admonition:: Example

    .. code-block:: text

        CUBES: index;x;y;z;kind;label;
        4;0;0;0;zxz;;
        3;3;0;0;xxz;;
        0;6;0;0;ooo;in_0;
        8;-6;0;0;ooo;out_0;

.. note::

    There is no fully-agreed denomination for open boundaries/ports or Y-cubes.
    For the time being, it is possible to use ``ooo`` or ``P`` for ports and ``Y``, ``yi``, ``ym`` to denote a Y-cube.

Pipes
~~~~~
Contains the information needed to translate each line of this section into a :code:`tqec` :ref:`Pipe <pipe>`.

The information in this section is meant to be parsed and must contain, at a minimum:

- ``src``: the ID of one of the pipe's two endpoints.
- ``tgt``: the ID of the other endpoint.
- ``kind``: the kind of the pipe (see :ref:`Pipe <pipe>` for all possibilities.).

Each Pipe item should be given as a CSV-separated sequence.
All separating semi-colons should be included and all fields should be given.

.. note::

    The block graph is **undirected**.
    The ``src`` and ``tgt`` labels are only a writing convention for the two endpoints of a pipe;
    swapping them describes the same edge, and no ordering or flow is implied.
    Pipes represent spacetime volumes between two cubes and are not inherently directional.
    The one exception is Hadamard pipes, whose *head* and *tail* ends carry a visualisation-only meaning
    inherited from the DAE importer (which end is the rotated one).

.. admonition:: Example

    .. code-block:: text

        PIPES: src;tgt;kind;
        4;3;oxz;
        4;5;zxo;
        4;6;oxz;
        16;18;ozxh;

General
-------
There are also a number of general practices to consider across sections.

Each section must include the header for the respective section, including the micro-schema for the section.
In other words, the following lines should appear exactly as in the examples given above.

- ``METADATA: attr_name; value;``
- ``CUBES: index;x;y;z;kind;label;``
- ``PIPES: src;tgt;kind;``

Additionally, the following terms are reserved for usage only as first item in the Metadata section.

- ``source``
- ``circuit_name``
- ``pipe_length``

For instance, it is not allowed to use the word ``source`` as the name of the graph in ``circuit_name``:

.. admonition:: Example

    .. code-block:: text

        METADATA: attr_name; value;
        circuit_name; source;

.. warning::

    This constraint is part of the BGRAPH specification but is not yet enforced by the :code:`tqec` parser.

Lastly, while probably obvious due to the nature of lattice surgery and the use of semi-colon-separated-values:

- the strings used as kinds for either cubes or pipes (e.g. ``zxz``, ``xxz``, ``oxz``, ``ozxh``, etc) should not be used for any other purpose.
- no additional semi-colons can be used anywhere in the field except as separators for the specific fields in each of the lines in metadata, cubes, or pipes sections.

Parsing a BGRAPH
----------------
If you have a BGRAPH file, you can easily convert it into a :code:`BlockGraph` using :code:`tqec`'s :code:`tqec.computation.block_graph.from_bgraph`.

.. jupyter-execute::

    from tqec import BlockGraph

    filepath = "../assets/cnots.bgraph"
    graph = BlockGraph.from_bgraph(filepath)

.. raw:: html

   <br>

You can then display and use the resulting :code:`BlockGraph` using other ``tqec`` methods.

For instance, you can call :code:`BlockGraph.view_as_html` to visualize the :code:`BlockGraph`.

.. jupyter-execute::

    graph.view_as_html()

.. raw:: html

   <br>

Additionally, you can attach the correlation surface to the model to visualize what the logical observable looks like:

.. jupyter-execute::

    correlation_surfaces = graph.find_correlation_surfaces()
    graph.view_as_html(
        pop_faces_at_directions=("-Y",),
        show_correlation_surface=correlation_surfaces[0],
    )

.. raw:: html

   <br>

And, of course, you can follow the same instructions available in several gallery docs (for instance, this :doc:`Steane code example </gallery/steane_encoding>`) to produce circuits and simulate the :code:`BlockGraph`.


Producing a BGRAPH
------------------
It is also possible to produce a BGRAPH of any ``tqec`` :code:`BlockGraph`.

In the example below, we print the BGRAPH string. To produce a `.bgraph` file with the contents of the string, simply change :code:`path_to_output_file=None` to Path (pathlib.Path or string).

.. jupyter-execute::

    from pathlib import Path
    from tqec.gallery import cnot
    from tqec.utils.enums import Basis

    # Import BlockGraph from gallery
    graph = cnot(Basis.X)

    # Write to BGRAPH
    bgraph_out_str = graph.to_bgraph(
        filepath=None,  # Change to a path to write output as `.bgraph`
        graph_name="cnot",
    )

    # Inspect BGRAPH string
    print(bgraph_out_str)

.. note::

     It is not allowed to use the reserved terms (``source``, ``circuit_name`` and ``pipe_length``) as the name of the graph in ``graph_name``.
