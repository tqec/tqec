``tqec`` architecture
=====================

This document is mainly targeted at a developer wanting to contribute to the
``tqec`` library. It provides a high-level overview of the different pieces that compose
the ``tqec`` library and how they interact with each other.

.. warning::

    This is a rapidly evolving project — codebase might change. If you encounter any
    inconsistencies, please open `an issue <https://github.com/tqec/tqec/issues/new/choose>`_.


This is done by presenting each of the sub-modules and their main classes / methods
in the order in which they are used internally to go from a topological computation to
an instance of ``stim.Circuit`` that can be executed on compatible hardware.

The diagram below provides a high-level overview of the dependencies between ``tqec``
submodules. It is not 100% accurate, as for example the ``tqec.circuit`` submodule
defines a few core data-structures that are used in ``tqec.plaquette``, but this is
the order in which the sub-modules will be covered here.

.. mermaid::
    :config: {"theme": "base", "darkMode": "true"}

    %%{
    init: {
        'theme': 'base',
        'themeVariables': {
        'primaryColor': '#AFEEEE',
        'lineColor': '#6495ED'
        }
    }
    }%%

    graph
        A[tqec.interop] --> B[tqec.computation]
        B --> E[tqec.compile]
        C[tqec.templates] --> E
        D[tqec.plaquette] --> E
        E --> F[tqec.circuit]
        F --> G[tqec.utils.noise_models]
        G --> H[tqec.simulation]

A user starts with a computation and an observable. The input computation can be provided as a :class:`.BlockGraph`
structure while an observable is represented as a correlation surface. The end goal of ``tqec`` is to generate a ``stim.Circuit``
such that the input is transformed into a topologically quantum error corrected quantum computation protected by a surface code.

.. _interop_ref:

:mod:`.interop`
--------------------

Allows a user to provide a ``.dae`` file or a ``pyzx`` graph as an input to ``tqec``.

* A :class:`.BlockGraph` can be constructed through a Collada ``.dae`` file through :func:`.read_block_graph_from_dae_file`
  and vice versa through :func:`.write_block_graph_to_dae_file`.
* A ZX graph can be mapped to a :class:`.BlockGraph` through :func:`.block_synthesis`.

Standard color representations as described in :ref:`terminology` are predefined in :class:`.TQECColor`.

Some conventional implementations of computations in ``.dae`` format are available in the :ref:`gallery-reference-label`.

:mod:`.computation`
--------------------

Defines data structures for the high-level :class:`.BlockGraph` representations of a fault-tolerant computation protected by the surface code.

The ``3D`` structures discussed in detail in :ref:`terminology` are defined in this module.

* A :class:`.CorrelationSurface` represents a set of parity measurements between the input and output logical operators.
* A :class:`.Cube` is a fundamental building block constituting of a block of quantum operations that occupy a specific spacetime volume.
  Quantum information encoded in the logical qubits can be preserved or manipulated by these blocks.
* A :class:`.Pipe` is a block that connects :class:`.Cube` objects in a :class:`.BlockGraph` but does not occupy spacetime volume on its own. The exception
  here are temporal hadamard pipes that have a volume when compiled using the fixed bulk convention.
* :class:`.PipeKind` helps determine the kind of a pipe in a  :class:`.BlockGraph` based on the wall bases at the head of the pipe in
  addition to a Hadamard transition.
* :class:`.Port` depicts the open ports in a :class:`.BlockGraph`.
* A :class:`.YHalfCube` represents Y-basis initialization and measurements.
* :class:`.ZXCube` defines cubes with only X or Z basis boundaries.


:mod:`.compile`
----------------

Responsible for translations between internal representations.

:class:`.BlockGraph` obtained from the functionality in :ref:`interop_ref` is further translated into a :class:`.TopologicalComputationGraph` represented
by :class:`.Block` instances.

.. mermaid::
    :align: center
    :config: {"theme": "base", "darkMode": "true"}

    %%{
    init: {
        'theme': 'base',
        'themeVariables': {
        'primaryColor': '#AFEEEE',
        'lineColor': '#6495ED'
        }
    }
    }%%

    graph
        A[BlockGraph] --> B[Topological <br> Computation Graph] --> C[ScheduledCircuit]--> D[stim.Circuit]

Multiple block builder protocols defined in ``tqec.compile.spec.library`` will take the high-level structure of a block to
templates and plaquettes, that can in turn be used to generate a fully annotated ``stim.Circuit``.

:mod:`.templates`
^^^^^^^^^^^^^^^^^

Generates an array of numbers representing a 2-dimensional, scalable, arrangement of plaquettes. This allows us to describe a
circuit that can scale the desired code distance.


:mod:`.plaquette`
^^^^^^^^^^^^^^^^^

A plaquette is the representation of a local quantum circuit. A surface code patch implements one layer in time or one round of the surface code. Same as
:mod:`.templates`, this module allows us to define scalable quantum circuits.


:mod:`.circuit`
^^^^^^^^^^^^^^^

Implementation of :class:`.ScheduledCircuit`, a quantum circuit representation in tqec, where each and every gate of a regular quantum circuit is associated with the time of execution. This module
maps from the numbered templates to some plaquettes that implement small local circuits to measure a stabilizer as a :class:`.ScheduledCircuit` instance.

:class:`.NoiseModel`
--------------------

.. note::

    The code for this module was modified from the code for :cite:`Gidney_inplace_access_2024`.

This module implements the following noise models for ``Stim`` simulations:

#. **Superconducting Inspired Circuit Error Model (SI1000)**: A modified version of the noise model introduced in :cite:`Gidney_si1000_2021` which represents the noise on Google's superconducting quantum chip.

    In :meth:`.si1000`:

    * Depolarizing noise on measured qubits from the noise modeil in :cite:`Gidney_si1000_2021` has been removed because ``tqec`` measurements are immediately followed by resets.

    * The measurement result is probabilistically flipped instead of the input qubit.

#. **Uniform Depolarizing Noise**: Single qubit depolarizing noise is uniformly applied to both single qubit and two qubit Clifford gates.

    In :meth:`.uniform_depolarizing`:

    * The result of dissipative gates is probabilistically bit or phase flipped.

    * Result of non-demolition measurements is flipped instead of the input qubit.



:mod:`.simulation`
-------------------

Utilities related to quantum circuit simulations through ``sinter``, a Python submodule in ``stim``.
Plotting functions are in this module too.



References
-----------
.. bibliography::
   :filter: docname in docnames
