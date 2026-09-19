Current known limitations
=========================

This page lists all the known limitations of the ``tqec`` library.

.. note::

    We aim at making this page as exhaustive as possible, but it will never be 100% exhaustive.
    If you think that this page is missing an important entry, please
    `raise an issue <https://github.com/tqec/tqec/issues/new/choose>`_ to let us know.

.. important::

    If any of the feature discussed below is important to you, please let us know!
    We will try to prioritize depending on community feedback. If you do not want to wait,
    please have a look at the :doc:`/contributor_guide` and open a pull request.

Spatial junctions
-----------------

A spatial junction is any cube that has at least 2 pipes in the spatial (``XY``) plane.
These kind of computation require special handling that is not currently implemented.

``Y``-basis measurements
------------------------

Walking codes
-------------

Transversal Hadamard gates for surface code
-------------------------------------------
