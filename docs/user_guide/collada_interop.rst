COLLADA Interoperability
========================

This notebook demonstrates how to interoperate :code:`tqec` with [COLLADA](https://en.wikipedia.org/wiki/COLLADA)( :code:`.dae`) files. COLLADA files can be
imported/exported to/from [SketchUp](https://www.sketchup.com/), which is a common used 3D modeling tool in QEC paper.

:code:`tqec` relies on [PyCollada](https://github.com/pycollada/pycollada) under the hood to realize the interoperability with COLLADA files.

Import COLLADA model
---------------------

A common workflow starting from SketchUp is:

1. Open the [template file](https://github.com/QCHackers/tqec/blob/main/assets/template.skp) in SketchUp.
2. Construct the model representing the logical computation.
3. Export the model as a COLLADA(:code:`.dae`) file from SketchUp.
4. Import the COLLADA file to :code:`tqec` as a :code:`BlockGraph`, which can be compiled to circuits.

:code:`tqec` provides the function :code:`tqec.interop.read_block_graph_from_dae_file` to import a COLLADA file as a :code:`BlockGraph`. Or you can
call :code:`BlockGraph.from_dae_file` directly.

.. jupyter-execute::

    from tqec import BlockGraph

    graph = BlockGraph.from_dae_file("../media/user_guide/logical_cnot.dae")

Export COLLADA model
---------------------

If you start with building the logical computation in :code:`tqec` and build a :code:`BlockGraph`, you can export the :code:`BlockGraph` to a COLLADA file by
calling :code:`BlockGraph.to_dae_file`.

.. jupyter-execute::

    graph.to_dae_file("logical_cnot.dae")

Display COLLADA model
---------------------

:code:`tqec` provides the function :code:`tqec.interop.display_collada_model` to view the COLLADA model as html and render it with [three.js](https://threejs.org/).
It can be used in IPython environment to display and play with the model interactively. You can also call :code:`BlockGraph.view_as_html` directly to first
convert it to a COLLADA model then display it.

.. jupyter-execute::

    graph.view_as_html()

Additionally, you can attach the correlation surface to the model to visualize what the logical observable looks like:

.. jupyter-execute::

    correlation_surfaces = graph.find_correlation_surfaces()
    graph.view_as_html(
        pop_faces_at_direction="-Y",
        show_correlation_surface=correlation_surfaces[0],
    )
