Terminology
===========

This page provides definitions for some important terms used in the ``tqec`` codebase.
Also, we highlight and expand on some concepts that can not fit in the :ref:`API Reference <api>`.

.. _block:

Block
-----

Represents quantum operations that encode some logical properties and are local in spacetime.
The quantum operations within the block are carefully designed to map logical operators in spacetime correctly.
At the same time, these operations generate syndrome information that protects the logical data, ensuring fault tolerance.

By composing blocks, we can construct the desired mappings between logical operators
while preserving the protection of the logical information.
This is the essence of fault-tolerant quantum computation.

In ``tqec``, a block is either a :ref:`Cube <cube>` or a :ref:`Pipe <pipe>`.

.. _cube:

Cube
----

Represents the fundamental building :ref:`block <block>` that occupies certain spacetime volume. The kind of cube determines the
quantum operations that are applied within the cube. Currently we have the following kinds of cubes, and more cubes can be added in the future:

.. figure:: ../media/user_guide/terminology/cubes.png
   :width: 400px
   :align: center

   Different kinds of cubes

.. _zxcube:

:py:class:`~tqec.computation.ZXCube`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A cube whose faces are of ``X`` (red) or ``Z`` (blue) type. We assume each pair of opposite faces are of the same type.
Then the kind can be specified by the type of the faces looking from the XYZ directions. For example, the `ZXZ` cube in the
figure above has ``Z`` type faces along the X direction, ``X`` type faces along the Y direction, and ``Z`` type faces along the Z direction.

A ``ZXCube`` occupies :math:`\approx d^3` spacetime volume, where :math:`d` is the code distance.

Note that ``ZXZ``, ``XZZ``, ``ZXX`` and ``XZX`` cubes can represent a (trivial) logical computation by themselves, i.e. a logical memory experiment.
For example, the ``XZX`` cube can be used to represent a logical qubit with ``Z``/``X`` boundaries parallel to the X/Y axes. And the time boundary
is of ``X`` type, which means that the logical qubit is initialized and measured in the logical ``X`` basis.

Spatial Junction
++++++++++++++++

Unlike the other ``ZXCube``, ``XXZ`` and ``ZZX`` cubes can not represent a logical computation by themselves. They need to be connected to other cubes
in space to form part of a logical computation:

.. figure:: ../media/user_guide/terminology/spatial_junctions.png
   :width: 450px
   :align: center

   Spatial junctions

The circuits that implement these spatial junctions are more complex than the circuits for the other cubes, and special care needs to be taken to avoid
the hook errors from decreasing the circuit-level code distance.

:py:class:`~tqec.computation.YCube`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A green cube representing inplace Y-basis logical initialization or measurement as proposed in `this paper <https://quantum-journal.org/papers/q-2024-04-08-1310/>`_.
The cube's function, whether for initialization or measurement, is determined by its connection to other cubes, either upwards or downwards.

A ``YCube`` occupies :math:`\approx d^3 /2` spacetime volume, where :math:`d` is the code distance.

:py:class:`~tqec.computation.Port`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A port is a special type of cube that represents the input or output of a logical computation.
It functions as a virtual cube, serving only as a placeholder for other sources or sinks of logical information.
Therefore, ports are not visualized in spacetime diagrams and occupy zero spacetime volume.

.. _pipe:

Pipe
----

Represents the :ref:`block <block>` that maps logical operators between different :ref:`cubes <cube>`.
There are various types of pipes based on the boundary types and connection direction. Additionally,
Hadamard transitions may occur in the pipe, which changes the basis of the logical operator passing through it.

.. figure:: ../media/user_guide/terminology/pipes.png
   :width: 500px
   :align: center

   Different types of pipes

**It's important to note that the pipe does not occupy spacetime volume by itself.**
Instead, the operations within the pipe replace the operations in the cubes it connects.
The pipe’s visual representation in the diagram is exaggerated for clarity.

.. figure:: ../media/user_guide/terminology/pipe_connects_cubes.png
   :width: 400px
   :align: center

   Example of pipes connecting cubes

Each cube in the figure above should initially be thought of as an

.. math::

   InitZ_k \rightarrow (2k − 1) \times Mem_k \rightarrow MeasZ_k

memory experiment. The pipes modify the walls of these experiments. The first vertical pipe should be interpreted as a layer of memory circuit :math:`Mem_k`.
It replaces :math:`MeasZ_k` in the bottom cube and :math:`InitZ_k` in the top cube with :math:`Mem_k` layers.
The horizontal pipe replaces the boundary walls of the two cubes it touches with connecting stabilizer measurements, along with appropriate data qubit initialization and measurement.

Correlation Surface
-------------------

A correlation surface in a computation is a set of measurements whose values determine the parity of the logical operators at the inputs and outputs associated with the surface.

The correlation surface establishes a mapping from the input logical operators to the output logical operators associated to it.
And the mapping implements the desired logical computation up to some sign that depends on the parity of the physical initialization,
measurements and stabilizer measurements included in the correlation surface. In ``tqec``, we assume all the qubits are initialized
to the +1 eigenstate of the operators. Therefore, the sign is determined by the parity of the measurements.

Here we take the movement of a logical qubit for example:

.. figure:: ../media/user_guide/terminology/logical_qubit_movement.png
   :width: 600px
   :align: center

   Movement of a logical qubit



The movement operation maps :math:`Z_L, X_L` logical operators at input to :math:`Z_L^{\prime}, X_L^{\prime}` at output.
Firstly, we show in detail why the structure and circuits above implement the movement of a logical qubit.

a. All data qubits initialized to :math:`|0\rangle`.
b. :math:`2k + 1` rounds of stabilizer measurement.
c. Beginning to extend the logical qubit with more data qubits initialized to :math:`|0\rangle`. Black dots represent data qubits doing nothing.
   :math:`Z_L` can be extended without sign change across these :math:`|0\rangle` values.
d. :math:`2k + 1` rounds of stabilizer measurement during which stabilizers indicated with red dots are used to move :math:`X_L`.
   The parity of any chosen round of these measurements sets a sign relationship between :math:`X_L` and :math:`X_L^{\prime}`.
   Our convention is to choose the earliest round.
e. :math:`Z` basis measurement of data qubits. The parity of the blue highlighted raw values sets
   a sign relationship between :math:`Z_L` and :math:`Z_L^{\prime}`.

Note that the sign relationship described above depends on the measurement outcomes, which are error-prone and need
error correction.

Tracking the process of logical operator movement above, we can get the following two correlation surfaces:

.. figure:: ../media/user_guide/terminology/correlation_surface.png
   :width: 200px
   :align: center

   Correlation surfaces, red for X and blue for Z

You can think of constructing the correlation surface as moving a line of logical operators through the structure,
only allowing the logical operators to attach to walls with the same basis.
The physical qubit measurements and stabilizer measurements in the correlation surface determine the sign relationship between the logical operators at the input and output.

.. _template:

Template
--------

In ``tqec``, a template is an object that can, from an integer value representing the
scaling factor $k$ (with the code distance $d$ checking $d = 2k + 1$ for the surface code),
can generate a $2$-dimensional array of positive integers.

.. _qubit_example:

.. admonition:: Example

   The following array is an example of what can be generated by a template::

      1  5  6  5  6  2
      7  9 10  9 10 11
      8 10  9 10  9 12
      7  9 10  9 10 11
      8 10  9 10  9 12
      3 13 14 13 14  4

The returned $2$-dimensional array entries each represent an index into a user-provided
mapping associating these indices to :class:`~tqec.plaquette.plaquette.Plaquette` instances.
The only exception is the value ``0`` that is associated to the absence of plaquette
by convention.

.. admonition:: Example

   The $2$-dimensional array given as example above can represent the usual logical qubit
   from surface code research papers:

   .. figure:: ../media/user_guide/terminology/logical_qubit.png
      :width: 200px
      :align: center

      Usual tiling of plaquettes to build a logical qubit using the surface code.

   To see the correspondence more clearly, one can map the indices ``1``, ``2``,
   ``3``, ``4``, ``5``, ``8``, ``12`` and ``14`` to the "no plaquette" index ``0``
   and print ``0`` with ``.`` for visual clarity::

      .  .  6  .  6  .
      7  9 10  9 10 11
      . 10  9 10  9  .
      7  9 10  9 10 11
      . 10  9 10  9  .
      . 13  . 13  .  .

Templates are the abstraction layer that allows most of ``tqec`` internals to be
independent of the chosen code distance.

Sub-template
------------

Sub-templates are defined as square $2$-dimensional arrays of fixed odd size. They are
systematically extracted from a contiguous portion of a larger template.

.. admonition:: Example

   The array::

      1  5  6
      7  9 10
      8 10  9

   is a valid sub-template of :ref:`the full example given in the Template <qubit_example>`
   section.


.. important::

   Sub-templates center (which is always well defined for a odd-sized square) is
   always extracted from a valid entry **within** the original template. The other
   sub-template entries *might* be extracted from outside the original template.

   The following sub-template::

      .  .  .  .  .
      .  1  5  6  5
      .  7  9 10  9
      .  8 10  9 10
      .  7  9 10  9

   is also a sub-template of :ref:`the full example given in the Template <qubit_example>`.
   Its top and left borders are filled with ``0`` (usually represented by a ``.``) because
   out-of-bounds accesses for templates are supposed to be ``0``.

Plaquette
---------

A plaquette is a specific quantum circuit. There are multiple bells and whistles
around that simple definition in ``tqec`` code, but all of them are due to implementation
details and do not matter here.

The quantum circuit represented by a plaquette are supposed to be:

1. spatially-local,
2. temporally-local,
3. with a fully explicit and precise gate scheduling.

Spatial locality means that the quantum circuit representing any plaquette should only use
a few qubits that are spatially close on a $2$-dimensional array grid of qubits.

Temporal locality means that the quantum circuit depth should be constant and short.

Explicit gate scheduling requires each and every gate in the circuit to be explicitly
scheduled at a precise time (or moment) in the quantum circuit.

These condition make plaquettes easily representable as visual $2$-dimensional pictures.

.. admonition:: Examples

   One of the plaquette measuring a ``XXXX`` stabilizer can be represented as follow

   .. figure:: ../media/user_guide/terminology/plaquette_xxxx.png
      :width: 100px
      :align: center

      ``XXXX`` plaquette.

   and corresponds to the following quantum circuit

   .. figure:: ../media/user_guide/terminology/circuit_xxxx.png
      :width: 500px
      :align: center

      Quantum circuit measuring the ``XXXX`` stabilizer.

   One of the plaquette measuring a ``ZZZZ`` stabilizer can be represented as follow

   .. figure:: ../media/user_guide/terminology/plaquette_zzzz.png
      :width: 100px
      :align: center

      ``ZZZZ`` plaquette.

   and corresponds to the following quantum circuit

   .. figure:: ../media/user_guide/terminology/circuit_zzzz.png
      :width: 500px
      :align: center

      Quantum circuit measuring the ``ZZZZ`` stabilizer.

   One of the plaquette measuring a ``XX`` stabilizer can be represented as follow

   .. figure:: ../media/user_guide/terminology/plaquette_xx_up.png
      :width: 100px
      :align: center

      ``XX`` plaquette.

   and corresponds to the following quantum circuit

   .. figure:: ../media/user_guide/terminology/circuit_xx_up.png
      :width: 500px
      :align: center

      Quantum circuit measuring the ``XX`` stabilizer.

Detector
--------

In the ``tqec`` library, a detector is a set of one or more measurements that are
supposed to have a deterministic parity in the absence of errors.
