Exact detector backend
======================

Select the experimental reference backend when generating a complete circuit::

    compiled = compile_block_graph(block_graph, observables="auto")
    circuit = compiled.generate_stim_circuit(k=1, detector_backend="exact")

Compilation discovers the complete independent correlation surfaces once, after
normalizing the graph. This internal metadata is independent of the selected
``observables``: ``None``, a subset, and ``"auto"`` produce the same detector
space. They only change emitted ``OBSERVABLE_INCLUDE`` instructions. Observable
annotation and internal logical metadata share measurement binding.

The backend extracts signed deterministic measurement checks :math:`C` from
identity-to-identity Stim flows of the complete noiseless circuit. External
stabilizers of the correlation surfaces define a binary symplectic dual of
logical Pauli operators. Physical logical strings implement these operators
after initialization or before final readout. Repeating Stim flow analysis
measures each check's response :math:`F` to those perturbations.

The allowed syndrome space is

.. math::

    S = \{xC \mid xF = 0\}.

Local detectors are preferred candidates. Those outside :math:`S` are removed;
missing independent directions are added until the detector span equals
:math:`S`. Completion favors low measurement weight, then short temporal and
spatial extent. This heuristic does not guarantee a graphlike detector basis.
The backend checks determinism, logical independence, and completeness, then
runs strict detector-error-model validation before applying noise.

For example, ``R 0; M 0; M 0`` has two deterministic measurement results. A
logical ``X`` after reset flips both. Only their parity is a syndrome check;
neither individual result becomes a detector, regardless of emitted observables.
Negative deterministic parities retain their sign throughout analysis. Stim's
reference sample accounts for their expected value when sampling detectors.

Limits and fallback
-------------------

This backend flattens repeat blocks and repeats global flow analysis for each
independent logical generator. It prioritizes correctness over large-circuit
performance. Physical string compilation currently supports regular leaf patches
in the fixed-bulk and fixed-boundary conventions. A dual can use other supported
leaves when a particular boundary has no string builder.

If full metadata is absent, no complete physical dual can be compiled, a bound
logical observable is not deterministic, or response validation fails, completion
is disabled. Only nondeterministic local candidates are removed; other local
candidates remain. A warning identifies metadata or physical-compilation failures.
No quotient by emitted observables, nor inference from local detectors, is used.
When automatic observable discovery itself fails, no automatic observables can
be emitted; the compiler warns and retains the filtering fallback. Explicitly
selected observables can still be emitted when their measurement binding succeeds.

Exact fault-distance validation requires SAT/MaxSAT on the full, undecomposed
detector error model, including hyperedges. Graphlike distance is
only a detector-basis quality metric: changing to an equivalent syndrome basis
can change which individual fault mechanisms appear graphlike.
