``tqec`` architecture
=====================

This document is mainly targeted at developer wanting to contribute to the
``tqec`` library. It gives a high-level overview of the different pieces that compose
the ``tqec`` library and how they interact with each other.

This is done by presenting each of the sub-modules and their main classes / methods
in the order in which they are used internally to go from a topological computation to
an instance of ``stim.Circuit`` that can be executed on compatible hardware.

The below diagram provides a high-level overview of the dependencies between ``tqec``
submodules. It is not 100% accurate, as for example the ``tqec.circuit`` submodule
defines a few core data-structures that are used in ``tqec.plaquette``, but this is
the order in which the sub-modules will be covered here.

.. mermaid::

    graph
        A[tqec.interop] --> B[tqec.computation]
        B --> E[tqec.compile]
        C[tqec.templates] --> E
        D[tqec.plaquette] --> E
        E --> F[tqec.circuit]
        F --> G[tqec.noise_models]
        G --> H[tqec.simulation]

``tqec.interop``
----------------

TODO

``tqec.computation``
--------------------

TODO

``tqec.compile``
--------------------

TODO

``tqec.templates``
------------------

TODO

``tqec.plaquette``
------------------

TODO

``tqec.circuit``
----------------

TODO

``tqec.noise_models``
---------------------

TODO

``tqec.simulation``
-------------------

TODO
