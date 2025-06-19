.. _installation:

How to install ``tqec``
=======================

Requirements
------------

Python version
~~~~~~~~~~~~~~

The ``tqec`` package only supports Python 3.10 and later. If you have Python 3.9 or earlier,
please update your Python installation.


Installation procedure
----------------------

(optional) Create a new environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is a good practice to create a new virtual environment for mananging the dependencies of the ``tqec`` package.

One way of doing that is using the native ``venv`` package of your python installation:

.. code-block:: bash

    python -m venv .venv
    # On GNU/Linux and MacOS
    source .venv/bin/activate
    # On Windows
    ## In cmd.exe
    .venv\Scripts\activate.bat
    ## In PowerShell
    .venv\Scripts\Activate.ps1

Install the ``tqec`` package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``tqec`` package is a regular Python package that can be installed using ``pip``.

It is not (yet) available on the official Python Package Index PyPI, so you will have
to manually provide the URL to install the package:

.. code-block:: bash

    python -m pip install git+https://github.com/tqec/tqec.git

And that's it! You can test the installation by running

.. code-block:: bash

    python -c "import tqec"

If the installation succeeded, the command should return without any message displayed.
Else, a message like

.. code-block::

    Traceback (most recent call last):
      File "<string>", line 1, in <module>
    ModuleNotFoundError: No module named 'tqec'

should appear.
