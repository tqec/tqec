"""Provide a flexible representation to define blocks.

The main data-structure provided by this module is
:class:`~tqec.compile.blocks.block.Block`, an abstract base class representing
a unit of quantum computation with defined spatial and temporal footprint.

This module provides two implementations of the :class:`~tqec.compile.blocks.block.Block`
abstract base class:

1. **LayeredBlock** - Represents blocks as a sequence of layers that can be instances
   of :class:`~tqec.compile.blocks.layers.atomic.base.BaseLayer` or
   :class:`~tqec.compile.blocks.layers.composed.base.BaseComposedLayer`. This is the
   standard representation for blocks that follow a layer-synchronous schedule.

2. **InjectedBlock** - Represents blocks via direct circuit representation using
   :class:`~tqec.compile.blocks.block.CircuitWithInterface`. 
   
The regular memory block follows the schedule::

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
in the resulting ``.stim`` file.

For LayeredBlock instances, this is handled by the layer merging system. For
InjectedBlock instances, this is handled by the :class:`~tqec.compile.tree.injection.InjectionBuilder`
which weaves injected circuits into layer-generated circuits while maintaining
correct detector annotations via flow interfaces from Gidney's gen library.

See Also
========

- :mod:`tqec.compile.blocks.layers` for layer representations
- :mod:`tqec.compile.tree.injection` for injection mechanics
- :mod:`tqec.compile.blocks.enums` for alignment and border enumerations

"""
