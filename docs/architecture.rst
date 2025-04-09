``tqec`` architecture
=====================

This document is mainly targeted at a developer wanting to contribute to the
``tqec`` library. It gives a high-level overview of the different pieces that compose
the ``tqec`` library and how they interact with each other.

.. warning::

    This is a rapidly evolving project - codebase might change. If you encounter any
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

A user starts with a computation and an observable. The computation is represented as a ``BlockGraph``
structure while the observable is represented as a correlation surface.

``tqec.interop``
----------------

This module allows a user to provide a ``.dae`` file or a ``pyzx`` graph as an input to ``tqec``. The gallery also
provides some implementations of standard computations (memory, CNOT, etc.).

Standard colors and 3D models imported from SketchUp.

``tqec.computation``
--------------------

BlockGraph representation of a computation.

Implements the BlockGraph structure using the surface code.

``tqec.compile``
--------------------

Translations between internal representations.

BlockGraph from everything in interop which is further translated into CompiledGraph

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
        A[BlockGraph] --> B[CompiledGraph] --> C[ScheduledCircuit]--> D[stim.Circuit]

Generating a stim.Circuit is the end goal of tqec. The input is transformed into a topologically quantum error
corrected quantum computation.

BlockBuilder will take the high-level structure of a block to templates and plaquettes.

SubstitutionBuilder encodes all the information needed to perform an operation to merge 2 logical qubits.

``tqec.templates``
------------------

Representation of a 2-dimensional, scalable, arrangement of plaquettes

Allow us to describe a circuit that scales the desired code distance.

Something that can generate an array of numbers.

``tqec.plaquette``
------------------

Representation of a local quantum circuit: Plaquette

Allow us to describe a circuit that scales the desired code distance.

A surface code patch implements one layer in time or one round of the surface code.

Mapping from the numbered templates to some plaquettes that implement small local circuits to measure a stabilizer.


``tqec.circuit``
----------------

Implementation of :class:`.ScheduledCircuit`, a quantum circuit representation in tqec, where each and every gate of a regular quantum circuit is associated with the time of execution.

``tqec.utils.noise_model``
--------------------------

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



``tqec.simulation``
-------------------

Utilities related to quantum circuit simulations through ``sinter``, a Python submodule in ``stim``.
Plotting functions are in this module too.

Additional information is available in :mod:`.simulation`.



References
-----------
.. bibliography::
