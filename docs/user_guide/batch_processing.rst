Batch processing
================

The package :mod:`tqec.orchestration` compiles many block graphs into noiseless circuits and then
samples them to estimate logical error rates. It runs in two stages that communicate only through
files in a run directory, so each stage can run as its own job.

- :py:func:`~tqec.orchestration.prepare_batch` checks each input (a ``.dae`` file, a ``.bgraph``
  file or a :py:class:`~tqec.computation.block_graph.BlockGraph`), selects its logical observables,
  compiles it and writes one ``.stim`` circuit per value of ``k``. It records what it built in
  ``manifest.json``.
- :py:func:`~tqec.orchestration.simulate_batch` reads that manifest, adds noise and runs one
  ``sinter.collect`` call over the whole batch. It writes ``results.json``.

.. code-block:: python

    from tqec.orchestration import BatchConfig, prepare_batch, simulate_batch

    config = BatchConfig(ks=(1, 2), ps=(1e-3,), max_shots=10_000)
    manifest = prepare_batch(["logical_cnot.dae"], config, "run_dir")
    result = simulate_batch("run_dir", num_workers=4)

    for row in result.results:
        print(row.gadget_id, row.k, row.p, row.decoder, row.shots, row.errors)

Every parameter of the run lives in :py:class:`~tqec.orchestration.BatchConfig`, which is stored in
the manifest, so the simulate stage needs no other input. Each entry of ``manifest.units`` is a
:py:class:`~tqec.orchestration.ManifestUnit` that records the status of one gadget, its circuits
and where its connected components sit in the input.

An input that holds several connected components is compiled as one circuit by default, with each
component keeping its own logical observables. Set ``BatchConfig(split_components=True)`` to
compile each component as its own gadget.
