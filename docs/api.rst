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
   utils.exceptions


Others
------

Some other objects that can be accessed from the top level module.


.. autosummary::
   :caption: Others
   :toctree: _autosummary
   :nosignatures:

   BlockPosition2D
   Direction3D
   PhysicalQubitPosition2D
   PlaquettePosition2D
   Position3D
   Shape2D
   Shift2D
   SignedDirection3D
   LinearFunction
   Scalable2D
   round_or_fail
   NoiseModel
   Orientation
