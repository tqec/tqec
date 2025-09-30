"""Provide a flexible representation to define blocks.

The main data-structure provided by this module is
:class:`~tqec.compile.blocks.block.Block`. It is able to represent in a flexible
manner anything that looks like a block in a topological computation represented
using SketchUp. In particular, that data-structure can be used to represent both
cubes and pipes.

In a topological computation, :class:`~tqec.compile.blocks.block.Block`
instances will happen in parallel, and ``tqec`` needs to account for that:
operations happening in parallel should be encoded in the same moment (i.e.,
between the same two ``TICK`` instructions) in the resulting ``.stim`` file.

Moreover, blocks might have different "schedules". For example, the regular
memory block follow the schedule:

1. initialisation layer,
2. repeat [memory layer],
3. measurement layer,

whereas a spatial pipe in the ``Y`` axis needs to alternate plaquettes in its
repeated layer, leading to a schedule that is:

1. initialisation layer,
2. repeat [memory layer 1 alternated with memory layer 2],
3. measurement layer.

All these restrictions are handled by representing
:class:`~tqec.compile.blocks.block.Block` instances with
:class:`~tqec.compile.blocks.layers.atomic.base.BaseLayer` and
:class:`~tqec.compile.blocks.layers.composed.base.BaseComposedLayer` instances.
See :mod:`tqec.compile.blocks.layers` for more details.

"""
