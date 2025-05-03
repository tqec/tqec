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

Currently, ``tqec`` is compatible with Python 3.10, 3.11 and 3.12. Some dependencies limit the project's
compatibility with Python 3.13.

.. code-block:: bash

    # Clone the repository to have local files to work on
    git clone https://github.com/tqec/tqec.git
    # Install the library with developer dependencies
    # Note the "-e" option, that's important.
    python -m pip install -e 'tqec[all]'
    # Go in the tqec directory and enable pre-commit
    cd tqec
    pre-commit install

.. warning::
    You will have to install ``pandoc`` separately as the instructions above only install a ``pandoc`` wrapper.
    See https://stackoverflow.com/a/71585691 for more info.

.. warning::
    The ``-e`` option to the ``python -m pip install`` call is **important** as it installs an editable version
    of ``tqec``. Without that option, changes made in the folder ``tqec`` will **not** be reflected on the
    ``tqec`` package installed.

    Without the ``-e`` option, ``pip`` copies all the files it needs (mainly, the code) to the current Python
    package folder. Any modification to the original ``tqec`` folder you installed the package from
    will not be reflected automatically on the copied files, which will limit your ability to test new
    changes on the code base. The ``-e`` option tells ``pip`` to create a link instead of copying, which means
    that the code in the ``tqec`` folder will be the code used when importing ``tqec``.

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
