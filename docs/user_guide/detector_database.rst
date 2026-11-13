Detector database
=================

Computing the detectors of a circuit can take long for large computations. ``tqec`` therefore keeps the detectors
it has already computed in a ``DetectorDatabase``. This page explains what the
database holds, where it is stored, and how a demo or a gallery example can ship its own database so that readers do not
have to recompute anything.

What the database stores
------------------------

A database maps a situation to the detectors found for it. A situation is a sub-template of the computation together
with the plaquettes used in each QEC round that the detectors span. Detectors are stored with coordinates relative to the
top-left qubit of the sub-template, so one entry serves every place where the same situation appears, in any block graph
and for any value of ``k``.

Where the default database lives
--------------------------------

Circuit generation functions take a ``database_path`` argument. It defaults to
``tqec.utils.paths.DEFAULT_DETECTOR_DATABASE_PATH``, a ``detector_database.pkl`` file in the per-user data
directory chosen by ``platformdirs``. The directory depends on the operating system, so print the path on your machine
with

.. code-block:: bash

    python -c "from tqec.utils.paths import DEFAULT_DETECTOR_DATABASE_PATH as p; print(p)"

Set the ``TQEC_DETECTOR_DATABASE_PATH`` environment variable to use another default file. It is read once, when
``tqec`` is imported, so set it before starting Python.

The file format follows the suffix of the path. ``.pkl`` and ``.pickle`` files are pickles and ``.json`` files are
JSON.

Generating and loading a database
---------------------------------

If ``database_path`` exists and ``detector_database`` is ``None``, the file
is loaded, and the loaded instance is saved back to the same path at the end of the generation, so a file that is
used this way can grow. If you pass an instance, it is used as is and, when ``database_path`` is not ``None``, it is saved to
``database_path`` at the end of the generation. If ``database_path`` does not exist and you pass no instance, ``tqec``
starts an empty database and creates the file at the end of the generation, so the next call can load it.

.. important::

    ``database_path`` defaults to the default database path, also when you pass ``detector_database``. Passing an
    instance without ``database_path`` therefore saves it over the file at the default path. Always pass
    ``database_path`` explicitly (a path of your own, or ``None`` to save nothing) together with ``detector_database``.

Shipping a database with a demo
-------------------------------

A demo that ships its database next to its source file lets readers generate the circuit without computing detectors.
Use JSON for a shared file. Pickle files are not portable between operating systems (see
`issue #681 <https://github.com/tqec/tqec/issues/681>`_), and loading a pickle runs arbitrary code.

The first snippet creates the database. It anchors the path to the directory of the script, so it does not depend on
where the script is launched from. In a notebook, where ``__file__`` is not defined, use ``Path.cwd()`` instead.

.. code-block:: python

    from pathlib import Path

    from tqec import compile_block_graph
    from tqec.compile.detectors.database import DetectorDatabase
    from tqec.gallery.memory import memory

    DATABASE_FILE = Path(__file__).parent / "demo_database.json"

    if __name__ == "__main__":
        database = DetectorDatabase()
        circuit = compile_block_graph(memory()).generate_stim_circuit(
            3,
            manhattan_radius=2,
            detector_database=database,
            database_path=DATABASE_FILE,
        )

When the database is empty or not used, detectors are computed in parallel worker processes, so a script that creates a database must keep the generation under an
``if __name__ == "__main__":`` guard, as above, on operating systems that start workers by importing the script (macOS
and Windows). Notebooks do not need the guard.

The snippet starts from an empty database and overwrites the file, so generate every value of ``k`` and every block
graph that the demo uses with the same database instance in one run, or extend the file as described in
`Updating the database`_. Then commit ``demo_database.json``. A shipped database is tied to the database format version
(``CURRENT_DATABASE_VERSION``) and to the detectors that the ``tqec`` code computes, so regenerate it after upgrading
``tqec``. A shipped database with an older format version raises an error when it is
passed as an instance (see `Load errors and version mismatches`_). The second snippet is what the demo does for its
readers. It loads the file, freezes it and does not write anything back. It passes ``recover_on_error=False`` so that a
broken shipped file raises an error, whereas the default would rename the file inside your repository.

.. code-block:: python

    from pathlib import Path

    from tqec import compile_block_graph
    from tqec.compile.detectors.database import DetectorDatabase
    from tqec.gallery.memory import memory

    DATABASE_FILE = Path(__file__).parent / "demo_database.json"

    if __name__ == "__main__":
        database = DetectorDatabase.from_file(DATABASE_FILE, recover_on_error=False)
        database.freeze()
        circuit = compile_block_graph(memory()).generate_stim_circuit(
            3,
            manhattan_radius=2,
            detector_database=database,
            database_path=None,
        )

A frozen database raises a :py:class:`~tqec.utils.exceptions.TQECError` if generation needs a detector that the file
does not contain, so a stale or incomplete file shows up as an error and not as a slow run. Leave out the call to
``DetectorDatabase.freeze`` if you prefer the missing detectors to be computed.

A relative ``database_path`` is resolved against the working directory of the process. The gallery examples use paths
such as ``Path("../_examples_database/database.pkl")``, which work because Sphinx-Gallery runs each script from its own
directory. Anchor the path to ``__file__`` when the script may be run from elsewhere.

Updating the database
---------------------

Entries are added when a generation computes detectors that the database does not have yet. To extend a shipped file for
a new block graph or a new ``k``, load it with ``DetectorDatabase.from_file(DATABASE_FILE, recover_on_error=False)``
without freezing it, generate the circuit with ``database_path`` set to the
same file, and commit the result. To regenerate a database from scratch, delete the file, or use a new
``database_path``, and run the first snippet again.

Load errors and version mismatches
----------------------------------

A database stores the version of the database format, in pickle and in JSON files (JSON files without a version are read
as version ``0.0.0``). ``tqec`` compares it with the version of the running code when it uses a database, see
`#1094 <https://github.com/tqec/tqec/pull/1094>`_. A mismatch has these effects:

- If you pass the database as ``detector_database``, ``tqec`` raises a :py:class:`~tqec.utils.exceptions.TQECError`.
  This is the case for the second snippet above.
- If you pass only a ``database_path`` other than the default one, ``tqec`` raises a
  :py:class:`~tqec.utils.exceptions.TQECError` and keeps the file.
- If the file is at the default path, ``tqec`` emits a warning, ignores the file and regenerates the database, which
  then replaces the file at the end of the generation.

If a file cannot be read, the result depends on how it is loaded, see
`#1135 <https://github.com/tqec/tqec/pull/1135>`_. When circuit generation loads the file at the default path, ``tqec``
renames it to ``faulty_database_<hash>.<extension>`` in the same directory, emits a warning, continues with an empty
database and writes a new file at the default path at the end of the generation. When it loads a file at another path, it raises a :py:class:`~tqec.utils.exceptions.TQECError` and keeps the
file. ``DetectorDatabase.from_file`` called directly renames an unreadable file unless you pass
``recover_on_error=False``. Delete or inspect a renamed file and regenerate the database.

The handling of version mismatches is still being refined, see issue
`#618 <https://github.com/tqec/tqec/issues/618>`_.
