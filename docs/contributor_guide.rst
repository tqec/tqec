Contributor guide
=================

This page explains how to contribute to ``tqec``:

- :ref:`contribution-process`, how to find an issue, open a pull request and get it merged, and the project's
  policies on AI use and automated review;
- :ref:`installation-procedure-for-developers`, how to set up a development environment;
- :ref:`building-documentation-locally` and :ref:`contributing-to-documentation`, how to build and extend these
  pages;
- :ref:`architecture-overview`, how the code base is organized.

.. _contribution-process:

Contribution process
--------------------

The process below is maintained in ``CONTRIBUTING.md`` at the root of the repository and included here, so that GitHub
and this page show the same text.

.. include:: ../CONTRIBUTING.md
   :parser: myst_parser.sphinx_
   :start-after: <!-- sphinx-include-start -->

.. _installation-procedure-for-developers:

Installation procedure (for developers)
---------------------------------------

If you want to help maintaining and improving the ``tqec`` package, you will need
to install a few more packages than the regular installation. It is also
recommended to use an editable installation.

Currently, ``tqec`` is compatible with Python 3.10, 3.11, 3.12 and 3.13. You can install the editable version
of ``tqec`` through ``pip`` or ``uv``.

.. hint::
    Creating an environment before running ``pip install`` is optional but recommended to avoid everything installing globally.
    Click `here <https://docs.python.org/3/library/venv.html>`_ for a common approach.

.. tab-set::

    .. tab-item:: pip

        .. code-block:: bash

            # Clone the repository to have local files to work on
            git clone https://github.com/tqec/tqec.git

            # Go in the tqec directory
            cd tqec

            # Update pip to at least v25.1
            python -m pip install --upgrade "pip>=25.1"

            # Install developer dependencies
            python -m pip install --group all
            # Install tqec in editable mode (the "-e" option)
            python -m pip install -e .
            # enable pre-commit
            pre-commit install

        .. attention::
            The ``-e`` option to the ``python -m pip install`` call is **important** as it installs an editable version
            of ``tqec``. Without that option, changes made in the folder ``tqec`` will **not** be reflected on the
            ``tqec`` package installed.

            Without the ``-e`` option, ``pip`` copies all the files it needs (mainly, the code) to the current Python
            package folder. Any modification to the original ``tqec`` folder you installed the package from
            will not be reflected automatically on the copied files, which will limit your ability to test new
            changes on the code base. The ``-e`` option tells ``pip`` to create a link instead of copying, which means
            that the code in the ``tqec`` folder will be the code used when importing ``tqec``.

    .. tab-item:: uv

        .. code-block:: bash

            # Clone the repository to have local files to work on
            git clone https://github.com/tqec/tqec.git
            # Go in the tqec directory
            cd tqec
            # Install the library with developer dependencies
            uv sync --group all
            # enable pre-commit
            uv run pre-commit install

        .. attention::
            Note that compared to ``pip``, we do not need to explicitly provide a flag for an editable installation in ``uv``.
            By default, ``uv sync`` will install an editable version of ``tqec``. Without the editable installation, changes
            made in the folder ``tqec`` will **not** be reflected on the installed ``tqec`` package.

            Without ``sync``, ``uv`` copies all the files it needs (mainly, the code) to the current Python
            package folder. Any modification to the original ``tqec`` folder you installed the package from
            will not be reflected automatically on the copied files, which will limit your ability to test new
            changes on the code base.


.. warning::
    You might have to install ``pandoc`` separately as the instructions above only install a ``pandoc`` wrapper, not
    the executable. See https://pandoc.org/installing.html for instructions.

If you encounter any issue during the installation, please refer to :ref:`installation` for more information.

.. _building-documentation-locally:

Building documentation locally
------------------------------

Install the documentation dependencies before building the docs:

.. tab-set::

    .. tab-item:: pip

        .. code-block:: bash

            python -m pip install --group docs

    .. tab-item:: uv

        .. code-block:: bash

            uv sync --group docs

If you also need the test dependencies, install both dependency groups:

.. tab-set::

    .. tab-item:: pip

        .. code-block:: bash

            python -m pip install --group docs --group test

    .. tab-item:: uv

        .. code-block:: bash

            uv sync --group docs --group test

There are two ways to build the documentation locally:

**Fast build** (recommended for iterating on docs content)
   Skips notebook execution and expensive examples. Significantly faster for quick feedback loops.

   .. code-block:: bash

       cd docs
       make fasthtml

   This build excludes:

   - Running the gallery examples (``docs/gallery/*.py``); their pages are built without output
   - Heavy simulation examples: ``quick_start``, ``detailed_plots``, ``collada_interop``, ``build_computation``, ``bgraph``

   Use this mode when editing documentation content, adding examples, or testing structure changes.

**Full build** (for final validation before opening a PR)
   Executes all notebooks and examples. Produces the complete documentation with all outputs.

   .. code-block:: bash

       cd docs
       make html

   Use this mode to:

   - Validate that all examples run correctly
   - Check outputs and visualizations
   - Before opening a pull request


If ``make html`` or ``make fasthtml`` reports that a Sphinx extension cannot be
imported, make sure the documentation dependencies were installed with
``uv sync --group docs`` from the repository root.

If you encounter unrelated warnings or issues during the build, consider opening an issue.

.. _contributing-to-documentation:

Contributing to documentation
-----------------------------

Executable examples are preferred over static code blocks when the example
depends on the ``tqec`` API. Running these blocks during the documentation build
helps us catch pages that have gone out of date after code changes.

Adding a page to the user guide
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

User guide pages are written in reStructuredText and stored in
``docs/user_guide``. To add a new page:

1. Create a new ``.rst`` file in ``docs/user_guide``.
2. Add the page to the appropriate ``toctree`` in ``docs/user_guide/index.rst``.
   This makes the page visible in the user guide navigation.
3. Use ``.. jupyter-execute::`` blocks for Python examples that should be run
   during the docs build.
4. Put images and other page-specific media in a matching subdirectory under
   ``docs/media/user_guide`` when possible.
5. If possible, build the documentation locally to verify your changes. Use
   ``make fasthtml`` for quick iteration, then ``make html`` before opening a PR
   to validate all examples run correctly.

Adding an example to the gallery
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Gallery examples are Python files stored in ``docs/gallery`` and processed
automatically by Sphinx-Gallery. Sphinx-Gallery generates the corresponding
documentation pages and Jupyter notebooks during the documentation build.

To add a new gallery entry:

1. Add the new Python example to ``docs/gallery``.
2. Use Sphinx-Gallery code-block markers such as ``# %%`` to separate
   executable sections of the example when appropriate.
3. Add the necessary narrative documentation as comments in the Python file.
4. Put generated or downloadable files for the example in a matching
   subdirectory under ``docs/media/gallery`` when possible.
5. Build the documentation locally to verify your changes. Use
   ``make fasthtml`` for quick iteration, then ``make html`` before opening a
   PR to validate the gallery examples.

Working with references
~~~~~~~~~~~~~~~~~~~~~~~

The documentation uses ``sphinxcontrib-bibtex`` for references. Add new BibTeX
entries to ``docs/refs.bib`` in alphabetical order by the first author's last
name. To cite an entry from a user guide page or gallery script, use the ``footcite`` role:

.. code-block:: rst

    :footcite:`CitationKey`

When adding a gallery example, write it as a standalone Python script (``.py``)
inside the ``gallery/`` directory. Use standard Sphinx-Gallery docstrings at
the top and ``# %%`` block comment markers to separate prose explanations and
headings from executable code.

For additional guidance on writing mathematical notations and LaTeX in
reStructuredText, see:

- `Math in reStructuredText <https://sphinx-nefertiti.readthedocs.io/latest/users-guide/components/math-rst.html>`_
- `ReStructuredText style guide <https://developer.lsst.io/v/DM-5973/docs/rst_styleguide.html>`_

Pages and notebooks that use references should end with a references section:

.. code-block:: rst

    References
    ----------

    .. footbibliography::

.. _architecture-overview:

Architecture overview
---------------------

A high-level overview of the different modules in ``tqec`` is available in :doc:`architecture`.

.. toctree::
   :hidden:

   architecture
