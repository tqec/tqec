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

This module provides one implementation of the :class:`~tqec.compile.blocks.block.Block`
abstract base class:

- **LayeredBlock** - Represents blocks as a sequence of layers that can be instances
  of :class:`~tqec.compile.blocks.layers.atomic.base.BaseLayer` or
  :class:`~tqec.compile.blocks.layers.composed.base.BaseComposedLayer`. This is the
  standard representation for blocks that follow a layer-synchronous schedule.

  Note that different blocks may have different schedules. For example, the
  regular memory block follows the schedule:

   1. initialisation layer,
   2. repeat [memory layer],
   3. measurement layer,

whereas a spatial pipe in the ``Y`` axis needs to alternate plaquettes in its
  repeated layer, leading to a schedule that is::

   1. initialisation layer,
   2. repeat [memory layer 1 alternated with memory layer 2],
   3. measurement layer.

Both of these can be represented as LayeredBlock instances.

Block Compilation
==================

In a topological computation, :class:`~tqec.compile.blocks.block.Block` instances
execute in parallel, and ``tqec`` must ensure that operations happening in parallel
are encoded in the same moment (i.e., between the same two ``TICK`` instructions)
in the resulting ``.stim`` file. This is handled by the layer merging system.

See Also
========

All these restrictions are handled by representing
:class:`~tqec.compile.blocks.block.Block` instances with
:class:`~tqec.compile.blocks.layers.atomic.base.BaseLayer` and
:class:`~tqec.compile.blocks.layers.composed.base.BaseComposedLayer` instances.

- See :mod:`tqec.compile.blocks.layers` for more layered block details.
- :mod:`tqec.compile.blocks.enums` for border enumerations

"""
