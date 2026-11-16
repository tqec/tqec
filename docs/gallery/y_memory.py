r"""Y Basis Memory
==============

This example demonstrates a logical memory experiment in the :math:`Y` basis. The logical
qubit is initialized and measured in the :math:`Y` basis inplace, with the construction of
:footcite:t:`Gidney_inplace_access_2024`.

Construction
------------

A :math:`Y` basis initialization or measurement is a Y half cube (see
:doc:`/user_guide/terminology`). It has three parts:

- a **transition** round that changes the boundaries of the patch from ``XZXZ`` to
  ``XXZZ`` with a diagonal domain wall. This maps the :math:`Y` observable to a known
  product of stabilizers,
- **padding** rounds that measure this product again and again, so that it is known with
  high certainty. The paper notes that "it's sufficient to measure these stabilizers d/2
  times",
- a **readout** round that measures one corner data qubit in the :math:`Y` basis and the
  other data qubits in the :math:`X` or :math:`Z` basis.

An initialization is the same block in reverse time order. Y half cubes are supported only
in the fixed-bulk convention.

``tqec`` provides the builtin function ``tqec.gallery.memory`` to construct a :math:`Y`
memory: one Y half cube initializes the qubit and a second one measures it.
"""

# ruff: noqa: E402

from tqec import PauliBasis
from tqec.gallery import memory

graph = memory(PauliBasis.Y)
# %%

graph.view_as_html()

# %%
# X top and Z top
# ---------------
#
# The Y half cube takes its orientation from the pipe that joins it to the next cube in
# time. The pipe sets the basis of the top and bottom boundaries of the patch. The graph
# above uses a ``ZXO`` pipe, so its top boundary is :math:`X` ("X top"). An ``XZO`` pipe
# gives the other orientation ("Z top"):

from tqec import BlockGraph
from tqec.utils.position import Position3D

graph_z_top = BlockGraph("Logical Y Memory Experiment, Z top")
bottom = graph_z_top.add_cube(Position3D(0, 0, 0), "Y")
top = graph_z_top.add_cube(Position3D(0, 0, 1), "Y")
graph_z_top.add_pipe(bottom, top, "XZO")

# %%
# The detectors of the transition round are computed by ``tqecd``. The Z top orientation
# (``XZO`` pipe) needs the minimal commuting cover of ``tqecd`` (tqec/tqecd#74). Without it,
# some Y half cubes lose detectors and the circuit distance falls to 1.
#
# Circuit
# -------
#
# The code below generates the ``d=3`` circuits of both orientations and builds links that
# open them, without noise, in Crumble.

from IPython.display import HTML

from tqec import compile_block_graph

links = []
for name, g in [("X top", graph), ("Z top", graph_z_top)]:
    url = compile_block_graph(g).generate_crumble_url(k=1)
    links.append(f'<a href="{url}">Open the d=3 {name} circuit in Crumble</a>')
HTML("<br>".join(links))

# %%
# References
# ----------
#
# .. footbibliography::
