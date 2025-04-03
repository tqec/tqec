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
        F --> G[tqec.noise_models]
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

BlockGraph from everything in interop which further translated into CompiledGraph

BlockGraph => CompiledGraph => ScheduledCircuit => stim.Circuit

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

Implementation of ScheduledCircuit - quantum circuit representation in tqec.

A regular quantum circuit where each and every gate is associated with the time of execution.

``tqec.noise_models``
---------------------

See :cite:t:`1987:nelson` for an introduction to non-standard analysis.
Non-standard analysis is fun\ :cite:p:`1987:nelson`.


``tqec.simulation``
-------------------

Utilities related to simulations through ``sinter``, a Python library. This is a submodule in ``stim`` which ``tqec`` uses
to simulate quantum circuits.

Plotting functions are in this module too.

References
-----------
.. bibliography::
