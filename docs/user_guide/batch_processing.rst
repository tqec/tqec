Batch processing
================

The package :mod:`tqec.orchestration` runs many computations in one go. It takes a list of inputs
(:code:`.dae` files, :code:`.bgraph` files or :code:`BlockGraph` objects). It compiles each one into
noiseless circuits, then samples them to estimate logical error rates (LER).

The work is split into two stages. The stages talk to each other only through files in a *run
directory*, so you can run them as separate jobs, even on different machines.

.. list-table::
   :header-rows: 1

   * - Stage
     - Function
     - Takes
     - Produces
   * - Prepare
     - :code:`prepare_batch`
     - Inputs, a :code:`BatchConfig`, a run directory
     - :code:`manifest.json`, :code:`circuits/*.stim`, :code:`graphs/`
   * - Simulate
     - :code:`simulate_batch`
     - A manifest, or the run directory
     - :code:`results.json`

Prepare checks each input, picks the logical observables, compiles the graph and writes one
noiseless :code:`.stim` circuit for each value of :code:`k`. Simulate adds noise, then runs one
:code:`sinter.collect` call over the whole batch. Inputs that fail in prepare are kept in the
manifest with an error status and are not sampled.

Minimal example
---------------

.. code-block:: python

    from tqec.orchestration import BatchConfig, prepare_batch, simulate_batch

    config = BatchConfig(ks=(1, 2), ps=(1e-3,), max_shots=10_000)
    manifest = prepare_batch(["logical_cnot.dae"], config, "run_dir")
    result = simulate_batch("run_dir", num_workers=4)

    for unit in manifest.units:
        print(unit.gadget_id, unit.status, unit.circuits)
    for row in result.results:
        print(row.gadget_id, row.k, row.p, row.decoder, row.shots, row.errors)

:code:`prepare_batch(inputs, config, output_dir, *, run_id=None, clean=False, progress=None)`
returns a :code:`BatchManifest` and writes it to :code:`output_dir/manifest.json`.

:code:`simulate_batch(manifest_or_path, *, save_resume_filepath=None, existing_data_filepaths=(),
progress=None, num_workers=None, custom_decoders=None, print_progress=False)` returns a
:code:`BatchResult` and writes :code:`results.json` to the run directory. If you pass
:code:`save_resume_filepath`, a killed run resumes from the saved statistics.
:code:`num_workers` defaults to the number of CPUs. Importing :code:`tqec.orchestration` does
not import :code:`sinter`. Only :code:`simulate_batch` does.

BatchConfig
-----------

:code:`BatchConfig` is a frozen dataclass. It is stored in the manifest, so the simulate stage
needs no other config file. All fields are optional.

.. list-table::
   :header-rows: 1

   * - Field
     - Default
     - Meaning
   * - :code:`conventions`
     - :code:`("fixed_bulk",)`
     - Convention names (keys of :code:`tqec.compile.convention.ALL_CONVENTIONS`).
   * - :code:`ks`
     - :code:`(1, 2)`
     - Values of :code:`k` to compile.
   * - :code:`ps`
     - :code:`(1e-3,)`
     - Physical error rates.
   * - :code:`noise_models`
     - :code:`("uniform_depolarizing",)`
     - Noise models. Known names: :code:`uniform_depolarizing`, :code:`si1000`.
   * - :code:`decoders`
     - :code:`("pymatching",)`
     - Decoder names.
   * - :code:`manhattan_radius`
     - :code:`2`
     - Manhattan radius used when compiling.
   * - :code:`max_shots`
     - :code:`10_000`
     - Stop after this many shots. At least one of :code:`max_shots` and :code:`max_errors` is required.
   * - :code:`max_errors`
     - :code:`None`
     - Stop after this many errors.
   * - :code:`max_batch_size`
     - :code:`None`
     - Largest sinter batch of shots.
   * - :code:`max_batch_seconds`
     - :code:`None`
     - Time limit for one sinter batch.
   * - :code:`expected_distance`
     - :code:`"2*k + 1"`
     - Recorded only. See :ref:`batch-limitations`.
   * - :code:`circuit_mode`
     - :code:`"materialized"`
     - :code:`"materialized"` or :code:`"streaming"`.
   * - :code:`logical_observables`
     - :code:`"all"`
     - Which correlation surfaces to use: :code:`all`, :code:`all_possible`,
       :code:`area_minimized` or :code:`random`.
   * - :code:`random_seed`
     - :code:`None`
     - Seed for the :code:`random` selection.
   * - :code:`split_components`
     - :code:`False`
     - Prepare each connected component as its own gadget. See below.

:code:`prepare_batch` calls :code:`BatchConfig.validate()` first and raises :code:`TQECError`
for an unusable config. :code:`to_dict` and :code:`from_dict` convert a config to and from JSON.

Monolithic mode and split mode
------------------------------

An input can hold several connected components, for example two independent memories in one
:code:`.dae` file.

By default (:code:`split_components=False`) the batch is *monolithic*. Each input is one gadget
and gives one circuit in one device frame. Each connected component keeps its own logical
observables. An observable that touches more than one component is rejected.

With :code:`split_components=True` each connected component becomes its own gadget and its own
circuit.

.. code-block:: python

    config = BatchConfig(split_components=True)

Both modes use the lattice positions of the input graph. Nothing is moved.

The manifest
------------

Each entry of :code:`manifest.units` is a :code:`ManifestUnit`. There is one unit per gadget and
convention. Besides :code:`gadget_id`, :code:`source`, :code:`status`, :code:`error`,
:code:`observables` and :code:`circuits` (a map from :code:`k` to a path relative to the run
directory), a unit records where its components sit:

- :code:`device_frame`: the bounding box of the whole input before any split, as
  :code:`{"minimum": [x, y, z], "maximum": [x, y, z]}`, inclusive, in lattice coordinates.
  It is :code:`None` when unknown. In split mode all units from one input share the same frame.
  A :code:`.dae` input split into pieces with different lattice phases has no shared frame, so
  its units record :code:`None`.
- :code:`components`: one record per connected component in this unit, with
  :code:`component_id`, :code:`minimum` and :code:`maximum`. Ids are :code:`c00`, :code:`c01`, ...
  in the order of :code:`BlockGraph.component_bounds()` of the whole input.
- :code:`observable_components`: the component id of each stim observable, indexed by observable
  index.

.. code-block:: python

    for unit in manifest.units:
        print(unit.gadget_id, unit.device_frame, unit.components, unit.observable_components)

The manifest stores unshifted lattice coordinates. The compiler moves the lowest occupied layer
to :code:`z = 0`, so the time axis of a circuit starts at the first occupied layer.

Manifests written by older versions still load. The three fields get empty defaults.

Component bounds
----------------

:code:`BlockGraph.component_bounds()` returns one :code:`ComponentBounds` per connected
component, sorted by the bounding box minimum in the order z, y, x. Only pipes that exist in the
graph connect cubes. An empty graph gives an empty list.

.. code-block:: python

    from tqec import BlockGraph

    graph = BlockGraph.from_dae_file("logical_cnot.dae")
    for bounds in graph.component_bounds():
        print(bounds.minimum, bounds.maximum, len(bounds.nodes))

:code:`ComponentBounds` has the fields :code:`nodes`, :code:`minimum` and :code:`maximum`
(inclusive corners) and the method :code:`overlaps(other)` for a bounding box test.

DAE import errors
-----------------

Reading a :code:`.dae` file raises :code:`TQECError` in these two cases, among others.

- *Lattice phase mismatch.* The cubes in the file do not all sit on one lattice. The message
  starts with "Cubes in the DAE file do not share one lattice phase" and names the axis. Move
  the cubes in SketchUp so they share a lattice, or split the file with
  :code:`tqec dae2batch`.
- *Two cubes on one lattice cell.* The message starts with "Two cubes land on the same lattice
  position" and gives both world positions. Remove or move one of the cubes.

The command-line tool
---------------------

The command :code:`tqec dae2batch` splits a :code:`.dae` file that holds several disjoint
structures into one file per structure. It does not run :code:`prepare_batch`.

.. code-block:: bash

    tqec dae2batch many_pieces.dae --out-dir pieces --bgraph

- :code:`-o`, :code:`--out-dir`: output directory. The default is :code:`<stem>_batch` next to the input.
- :code:`--bgraph`: also convert each piece to a :code:`.bgraph` file.
- :code:`--clean`: remove old output files from the output directory first.

The output files are named :code:`<stem>_batch<NN>`. With :code:`--bgraph` the command exits with a
nonzero status if some pieces fail to convert. The pieces that worked are still written.

.. _batch-limitations:

Limitations
-----------

- There is no fault-distance stage. :code:`BatchConfig.expected_distance` is stored but nothing
  reads it.
- There is no command-line flag for :code:`split_components`, and no command that runs
  :code:`prepare_batch` or :code:`simulate_batch`. Use the Python API.
- A block graph with an unoccupied z value between two occupied ones fails at circuit
  generation with a :code:`TQECError` ("An instance of SequencedLayers is expected to have at
  least one layer"). The unit is recorded as failed at the circuit stage.
- LER is reported per unit. Combining the LER of several components into one number is not
  provided.
