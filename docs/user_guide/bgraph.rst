BGRAPH
========================

BGRAPH is a work-in-progress file format (`.bgraph`) that can be used to facilitate interoperability between external lattice surgery (LS) tools.

While only a preliminary minimum baseline in need of improvement, the current BGRAPH specification already enjoys the following advantages:
- Common format both `Topologiq <https://github.com/tqec/topologiq>` and `TopoLS <https://github.com/tqec/TopoLS>` can produce
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

An example BGRAPH file is available from :code:`tqec.assets`, `here <https://github.com/tqec/tqec/blob/main/assets/cnots.bgraph>`.

HEADER
~~~~~~
Contains the file header. The information in this section is for identification purposes and is not meant to be parsed.

::
    BLOCKGRAPH 0.1.0;

METADATA
~~~~~~~~
Contains the information needed to produce a blockgraph using the information available in other sections.

The information in this section is parseable, but the specific fields are optional:
- length of pipes used in the source tool: The length of the pipes between any two adjacent cubes (see note 1, at the end of this section).
- name of the circuit: used to give the blockgraph a reference name.

Each METADATA item should be given as a CSV-separated pair. If a field is not included, TQEC will assign default values.

::
    METADATA: attr_name; value;
        source; name_of_tool_that_created_the_file;
        pipe_length; 2.0;
        circuit_name; CNOTs;

*Note 1. All pipes measure exactly the same. In TQEC, cubes are immediately adjacent, which means `pipe_length` is 0.0. However, this is a TQEC convention. Other software can and do use longer pipes.*

CUBES
~~~~~
Contains the information needed to translate each line of this section into a :code:`tqec` `cube <./terminology.rst>`.

The information in this section is meant to be parsed and must contain, at a minimum:
- index: the ID of the cube, typically an integer.
- position: The (x, y, z) position of the cube, a tuple of integers.
- kind: The kind of the cube, as a string (see `Terminology <https://tqec.github.io/tqec/user_guide/terminology.html>`, as well as note 2).
- label (optional): An optional annotation that is typically used to denote when a cube is a PORT.

Each CUBE item should be given as a CSV-separated sequence.

::
    CUBES: index;x;y;z;kind;label;
    4;0;0;0;zxz;;
    3;3;0;0;xxz;;
    0;6;0;0;ooo;in_0;
    8;-6;0;0;ooo;out_0;

    ...

*Note 2. There is not fully-agreed denomination for open boundaries/ports or Y-cubes. For the time being, it is possible to use "ooo" or "P" for ports and any arbitrary string containing a "y" to denote a Y-cube.

PIPES
~~~~~
Contains the information needed to translate each line of this section into a :code:`tqec` `pipe <./terminology.rst>`.

The information in this section is meant to be parsed and must contain, at a minimum:
- index: the ID of the cube, typically an integer.
- u: The ID of the cube at which the pipe starts (the source for the edge represented by the pipe).
- v: The ID of the cube at which the pipe ends (the target for the edge represented by the pipe).
- kind: The kind of the pipe (see `Terminology <https://tqec.github.io/tqec/user_guide/terminology.html>` for all possibilities.).

Each PIPE item should be given as a CSV-separated sequence.

::
    PIPES: src;tgt;kind;
    4;3;oxz;
    4;5;zxo;
    4;6;oxz;
    16;18;ozxh;

    ...

Producing a BGRAPH
------------------
There is not specific way in which a BGRAP should be created. As long as the information is there, the file will be parsable.


Parsing a BGRAPH
----------------

If you have a BGRAPH file, you can easily convert it into a blockgraph using :code:`tqec`.

:code:`tqec` provides the method:code:`tqec.computation.block_graph.from_bgraph` to easily build a :class:`BlockGraph` from a BGRAPH file.

.. jupyter-execute::

    from tqec import BlockGraph

    filepath = "../assets/cnots.bgraph"
    graph = BlockGraph.from_bgraph(filepath=filepath)

You can then display and use the resulting blockgraph using other TQEC methods.

For instance, to visualise, :code:`tqec` provides the function :code:`tqec.interop.display_collada_model` to view the blockgraph as html. It can be used in IPython environment to display and play with the model interactively. You can also call :code:`BlockGraph.view_as_html` directly to first
convert it to a COLLADA model then display it.

.. jupyter-execute::

    graph.view_as_html()

Additionally, you can attach the correlation surface to the model to visualize what the logical observable looks like:

.. jupyter-execute::

    correlation_surfaces = graph.find_correlation_surfaces()
    graph.view_as_html(
        pop_faces_at_directions=("-Y",),
        show_correlation_surface=correlation_surfaces[0],
    )

And, of course, you can follow the same instructions available in several other docs to produce circuits and simulate the blockgraph.
