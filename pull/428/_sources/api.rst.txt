.. _api:

API Reference
=============

This section documents the API of the :mod:`tqec` package.

Modules
------------------

A list of structural modules in the package. Some of the functions and classes in the submodules are imported
into the :mod:`tqec` namespace and can be accessed at the top level.

.. currentmodule:: tqec

.. autosummary::
   :caption: Modules
   :toctree: _autosummary

   templates
   plaquette
   circuit
   computation
   compile
   gallery
   interop
   simulation
   exceptions


Others
------

Some other objects that can be accessed from the top level module.


.. autosummary::
   :caption: Others
   :toctree: _autosummary
   :nosignatures:

   Interval
   Direction3D
   Displacement
   Position2D
   Position3D
   Shape2D
   SignedDirection3D
   LinearFunction
   Scalable2D
   round_or_fail
   NoiseModel
