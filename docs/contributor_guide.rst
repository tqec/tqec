How to contribute
=================

Architecture Overview
---------------------

A high-level overview of the different modules in ``tqec`` is available in

.. toctree::
   :maxdepth: 1

   architecture

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
            python -m pip install --upgrade pip>=25.1

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
            # Note the "-editable" option, that's important.
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
    You might have to install ``pandoc`` separately as the instructions above only install a ``pandoc`` wrapper.
    See https://stackoverflow.com/a/71585691 for more info.

If you encounter any issue during the installation, please refer to :ref:`installation` for more information.

You can now start contributing, following the rules explained in the next sections.

How to contribute
-----------------

1. Look at issues
~~~~~~~~~~~~~~~~~

Start by looking at the `issues list <https://github.com/tqec/tqec/issues>`_.
Issues can be filtered by tags. Below are a few of the most interesting tags:

- `good first issue <https://github.com/tqec/tqec/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22>`_
  for issues that have been judged easy to address without prior knowledge on the code base.
- `backend <https://github.com/tqec/tqec/issues?q=is%3Aissue+is%3Aopen+label%3Abackend>`_
  for issues related to the Python code.

Pick one issue that you **want** to work on. We emphasize on **want**: this is an open
source project, so do not force yourself to work on something that does not interest
you.

2. Comment on one or more issues
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once you have found one or more issue(s) you want to work on, send a comment on these
issues to:

1. make your interest public,
2. ask for updates, as the issue might not be up-to-date.

One of the lead developers will come back to you and assign you the issue if

1. nobody is already working on it,
2. the issue is still relevant.

3. Create a specific branch for each issue
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are a part of the tqec community, you will be able to
`create a branch <https://git-scm.com/book/en/v2/Git-Branching-Basic-Branching-and-Merging>`_
directly in the tqec repository. If you are not, you can
`fork <https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo>`_
the tqec repository on your own account
(`click here <https://github.com/tqec/tqec/fork>`_) and create a branch there.

4. Work in your branch and submit a pull request
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You should only work on the branch you just created. Implement the fix you envisioned
to the issue you were assigned to.

If, for personal/professional reasons, lack of motivation, lack of time, or whatever
the reason for which you know that you won't be able to complete your implementation, please
let us know in the issue so that we can un-assign you and let someone else work on
the issue.

Once you think you have something that is ready for review or at least ready to be read
by other people, you can
`submit a pull request (PR) <https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request>`_
on the ``main`` branch of the tqec repository. In the PR message, try to
provide as much information as possible to help other people understanding your code.

5. Merge the PR
~~~~~~~~~~~~~~~

Once your code has been reviewed and accepted by at least one of the developers, you
will be able to merge it to the ``main`` branch.
You (the PR owner) are responsible to click on the "Merge" button. If you prefer someone
else to do it, you should send a clear comment asking for it.

Contributing to Documentation
------------------------------

The ``tqec`` documentation is built using Sphinx and includes both a user guide and an
example gallery. This section explains how to add new content to either.

How to add a page to the user guide
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The user guide pages are located in ``docs/user_guide/`` and written in reStructuredText
(``.rst``) format. Here's how to add a new page:

1. **Create a new .rst file** in ``docs/user_guide/``

   Name your file descriptively (e.g., ``advanced_compilation.rst``). Start with a title:

   .. code-block:: rst

       My Page Title
       =============

2. **Add your content using reStructuredText**

   See the `Sphinx reStructuredText documentation <https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html>`_
   for syntax reference. Common elements include:

   - **Sections**: Use ``=====`` under titles, ``-----`` for subsections
   - **Code blocks**: Use ``.. code-block:: python`` for static code
   - **Executable code**: Use ``.. jupyter-execute::`` for code that runs during the docs build
   - **Links**: Use ``:ref:`label-name``` to reference other pages

3. **Use executable code blocks when possible**

   The ``tqec`` documentation uses `jupyter-sphinx <https://jupyter-sphinx.readthedocs.io/en/latest/>`_
   to execute code during the documentation build. This ensures examples stay up-to-date:

   .. code-block:: rst

       .. jupyter-execute::

           from tqec import BlockGraph
           # Your working code here
           print("This code will be executed during docs build")

   .. warning::
       Make sure your code executes quickly (< 30 seconds) to avoid slowing down the docs build.

4. **Add references if needed**

   If you cite academic papers or external resources:

   a. Add the reference to ``docs/refs.bib`` in alphabetical order by last name:

      .. code-block:: bibtex

          @article{AuthorName_2024,
             title={Paper Title},
             ...
          }

   b. Cite in your ``.rst`` file using ``footcite``:

      .. code-block:: rst

          This approach was introduced by [<cite data-footcite-t="AuthorName_2024"></cite>].

   c. Add a References section at the bottom of your page:

      .. code-block:: rst

          References
          ----------
          .. footbibliography::

5. **Add your page to the index**

   Edit ``docs/user_guide/index.rst`` and add your page to the ``toctree``:

   .. code-block:: rst

       .. toctree::
          :maxdepth: 2

          installation
          quick_start
          my_new_page

6. **Build the docs locally to verify**

   .. code-block:: bash

       # From the repository root
       cd docs
       make html
       # View the result by opening docs/_build/html/index.html in a browser

   Check that:

   - Your page appears in the navigation
   - All code blocks execute successfully
   - Images and links work correctly
   - References render properly

How to add an example to the docs gallery
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The gallery showcases complete computation examples and is located in ``docs/gallery/``.
All gallery examples are Jupyter notebooks that are executed during the documentation build.

1. **Create a Jupyter notebook**

   Create your notebook in ``docs/gallery/`` with a descriptive name (e.g., ``my_computation.ipynb``).

2. **Structure your notebook**

   Start with a markdown cell containing the title and description:

   .. code-block:: markdown

       # My Computation Title

       This notebook demonstrates how to [describe your example].

   Follow with sections:

   - **Construction**: Show how to build the block graph
   - **Observables**: Demonstrate finding correlation surfaces
   - **Compilation**: Compile and generate the circuit
   - **Visualization**: Show plots or interactive views

3. **Clear all outputs before committing**

   .. important::
       Gallery notebooks **must** have their outputs cleared before committing.
       This allows the documentation build process to execute them and ensures
       they remain up-to-date with code changes.

   To clear outputs:

   - In Jupyter: ``Cell > All Output > Clear``
   - Command line: ``jupyter nbconvert --clear-output --inplace your_notebook.ipynb``

4. **Use references if needed**

   Add citations using the ``footcite`` format in markdown cells:

   .. code-block:: markdown

       This technique is from [<cite data-footcite-t="Fowler_2012"></cite>].

   Add a References section at the end:

   .. code-block:: markdown

       ## References

   .. code-block:: rst

       .. footbibliography::

   Remember to add any new references to ``docs/refs.bib``.

5. **Add your notebook to the gallery index**

   Edit ``docs/gallery/index.rst`` and add your notebook:

   .. code-block:: rst

       .. nbgallery::

          memory.ipynb
          cnot.ipynb
          my_computation.ipynb

6. **(Optional) Add a thumbnail**

   If you want a custom thumbnail for your example:

   a. Create a PNG image (recommended size: 400x300px)
   b. Place it in ``docs/_static/media/gallery/``
   c. Edit ``docs/conf.py`` and add to ``nbsphinx_thumbnails``:

      .. code-block:: python

          nbsphinx_thumbnails = {
              "gallery/my_computation": "_static/media/gallery/my_computation.png",
              ...
          }

7. **Test your notebook**

   Ensure your notebook executes cleanly:

   .. code-block:: bash

       # Test the notebook runs without errors
       jupyter nbconvert --execute --to notebook my_computation.ipynb

       # Build the docs to verify integration
       cd docs
       make html

   .. warning::
       Keep execution time reasonable (< 2 minutes per notebook) to avoid
       slowing down the documentation build.

Best Practices for Documentation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**For both user guide pages and gallery examples:**

- **Keep code executable**: Use ``jupyter-execute`` in user guide pages and ensure
  gallery notebooks run successfully. This catches breaking changes automatically.
- **Be concise**: Focus on demonstrating one concept or workflow per page/notebook.
- **Test thoroughly**: Always build the docs locally before submitting a PR.
- **Use clear titles**: Make it easy for users to find what they need.
- **Add context**: Explain why someone would use this approach, not just how.
- **Cross-reference**: Link to related pages using ``:ref:`` directives.

**Code examples should:**

- Import all necessary modules explicitly
- Use realistic but simple examples
- Include comments explaining non-obvious steps
- Avoid long-running computations in docs builds
- Handle any required assets (like ``.dae`` files) appropriately

Common pitfalls to avoid
~~~~~~~~~~~~~~~~~~~~~~~~

1. **Committing notebooks with outputs**: Always clear outputs before committing.
2. **Long execution times**: Keep code blocks fast to avoid slow documentation builds.
3. **Hard-coded paths**: Use relative paths that work in the docs build environment.
4. **Missing dependencies**: Ensure all imports work with the standard dev installation.
5. **Forgetting to update indices**: Always add new pages to the appropriate index file.
6. **Inconsistent formatting**: Follow the style of existing pages for consistency.
