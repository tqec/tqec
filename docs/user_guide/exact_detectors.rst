Exact detector backend
======================

Select the experimental reference backend when generating a complete circuit::

    compiled = compile_block_graph(block_graph, observables="auto")
    circuit = compiled.generate_stim_circuit(k=1, detector_backend="exact")

Compilation discovers the complete independent correlation surfaces once, after
normalizing the graph. Internal logical metadata is independent of the selected
``observables``: ``None``, a subset, and ``"auto"`` produce the same detector
space. They only change emitted ``OBSERVABLE_INCLUDE`` instructions. Observable
annotation and internal logical metadata share measurement binding.

Open logical boundaries
-----------------------

The analysis circuit preserves logical input/output Paulis instead of closing
them with fixed initialization and destructive logical readout. This is an
analysis-only circuit: the returned experimental circuit retains its physical
initialization, gates, readouts, and measurement numbering.

Opening a boundary does **not** mean removing every data-qubit reset or readout.
That would also remove the boundary stabilizer constraints and lose valid
syndrome checks. For a regular patch, the observable builders give a crossing
pair of physical logical lines. A Clifford decoder maps this pair onto their
single intersection qubit:

* At an input, swap an unreset external port into the intersection qubit and
  apply the inverse decoder. The remaining initialization constraints survive.
* At an output, decode and swap the logical qubit into an external output port.
  Measure the remaining qubits. Their outcomes are logical-independent parities
  with an explicit linear map back to the original measurement records.
  The vacated intersection qubit produces a known-zero dummy record.

For example, a Z-memory exposes ``Z_in -> Z_out``. A CNOT exposes its X and Z
logical propagation relations, with intermediate measurements accounting for
Pauli-frame corrections. The complete correlation surfaces and their shared
measurement binding specify the flows that must be present; independent
external-boundary directions and flow signs are checked before completion.

Flow elimination
----------------

On the successful path, the backend calls ``flow_generators()`` **once**, on the
complete noiseless analysis circuit. GF(2) elimination cancels all input/output
Pauli columns. Stim Pauli-string multiplication preserves phases during this
elimination, including products of anticommuting input/output operators.

The resulting identity-to-identity measurement checks, mapped back to the
original circuit records, span the syndrome space :math:`S`. Local detectors
are preferred candidates. Those outside :math:`S` are removed; missing independent
directions are added until the detector span equals :math:`S`. Completion favors
low measurement weight, then short temporal and spatial extent. This heuristic
does not guarantee a graphlike detector basis. Finally, strict detector-error-model
validation runs before noise is applied.

For example, opening the input of ``R 0; M 0; M 0`` gives two flows with the same
input Z and different measurement records. Multiplying them cancels the input
Pauli, leaving only the parity of the two results as a detector. Neither result
individually becomes a detector, regardless of emitted observables.

Negative deterministic parities retain their sign throughout analysis. Stim's
reference sample accounts for their expected value when sampling detectors.
There are no logical Pauli perturbations, repeated circuit analyses per logical
generator, or quotients by emitted observables.

Limits and fallback
-------------------

This backend flattens repeat blocks and uses global flow algebra. It prioritizes
correctness over large-circuit performance. Boundary encoding currently supports
regular leaf patches in the fixed-bulk and fixed-boundary conventions. Spatial
leaves without an encoder stay closed; completion is permitted only if the
exposed ports still distinguish every independent correlation surface and all
expected flows validate.

Missing metadata, unsupported boundary compilation, or failed flow validation
disables completion. The original closed circuit is then analyzed to remove only
nondeterministic local candidates; other local candidates remain. A warning
identifies compilation or validation failures. No logical semantics are inferred
from local detectors. When automatic surface discovery fails, the compiler warns
and emits no automatic observables; explicitly selected observables can still
be emitted when their binding succeeds.

Exact fault-distance validation requires SAT/MaxSAT on the full, undecomposed
detector error model, including hyperedges. Graphlike distance is only a
basis-quality metric. Completing detectors also cannot repair a physical
low-weight logical fault: the fixed-boundary k=1 circuit in issue #1000 has
complete syndrome rank but still admits a two-fault logical error.
