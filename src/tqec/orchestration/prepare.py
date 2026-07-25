"""Normalize inputs into gadgets, compile them, and write ``manifest.json``.

:func:`prepare_batch` takes a mixed sequence of inputs--``.dae`` files, ``.bgraph`` files,
and in-memory :class:`~tqec.computation.block_graph.BlockGraph` objects--splits each into its
constituent gadgets, and walks every gadget through validate -> resolve observables -> compile
-> generate noiseless circuits. Each gadget lands in the run directory as a noiseless
``.stim`` file per ``k``; ``manifest.json`` records what was built.

No noise model is involved here--that is entirely the simulate stage's concern--so one
prepare can feed many noise models or supply an program specification for
further compilation or execution. This module imports neither :mod:`sinter`
nor (at import time)
:mod:`collada`; the DAE-specific helpers are imported lazily inside the ``.dae`` route so a
prepare-only or manifest-inspecting environment need not have them installed.

Observable keying: a closed gadget yields one unit whose ``gadget_id`` is the base id.
For an open graph, TQEC selects correlation surfaces according to
``BatchConfig.logical_observables`` and groups compatible surfaces into measurement settings.
Each setting becomes a distinct manifest gadget. The selected surfaces are the user-facing
specification; the concrete cube placed at each port is recorded as derived provenance.

TODO: Multiprogramming may be useful here to emit circuits for multiple gadgets in parallel.
"""

from __future__ import annotations

import hashlib
import os
import random
import re
import sys
import warnings
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import reduce
from itertools import combinations
from pathlib import Path
from typing import TYPE_CHECKING

from tqec.compile import compile_block_graph
from tqec.compile.convention import ALL_CONVENTIONS
from tqec.computation.block_graph import BlockGraph
from tqec.computation.correlation import reduce_observables_to_minimal_generators
from tqec.computation.open_graph import (
    fill_ports_for_minimal_simulation,
    fill_ports_for_observables,
)
from tqec.interop.bgraph import read_bgraph
from tqec.orchestration.mode import write_circuit
from tqec.orchestration.schema import (
    BatchConfig,
    BatchFailure,
    BatchManifest,
    LogicalObservableSelection,
    ManifestUnit,
    ResolvedLogicalObservable,
    UnitStatus,
)
from tqec.utils.exceptions import TQECError, TQECWarning

if TYPE_CHECKING:
    from tqec.computation.correlation import CorrelationSurface

# Gadget-level errors that are recorded terminally rather than aborting the batch. ``TQECError``
# covers rejected graphs and non-deterministic observables; ``NotImplementedError`` covers
# convention features not yet built. Interrupts and genuine programming errors
# (``AttributeError``, ``TypeError``, ...) are not caught and propagate.
_EXPECTED_GADGET_ERRORS = (TQECError, NotImplementedError)

_CONV_SUFFIX = {"fixed_bulk": "bulk", "fixed_boundary": "boundary"}

# One split product: ``(source, gadget_id, graph, error_message, error_type)``. A ``graph`` of
# ``None`` marks an import failure; ``error_message`` and ``error_type`` carry its message and the
# real exception type name. Success rows leave both trailing fields ``None``.
_GadgetRow = tuple[str, str, "BlockGraph | None", "str | None", "str | None"]


@dataclass(frozen=True)
class _ObservableFilling:
    """One compilation-ready graph and its selected logical observables."""

    gadget_id: str
    graph: BlockGraph
    observables: list[CorrelationSurface]
    resolved_observables: tuple[ResolvedLogicalObservable, ...]
    derived_port_cube_kinds: dict[str, str] | None


def prepare_batch(
    inputs: Sequence[str | Path | BlockGraph],
    config: BatchConfig,
    output_dir: str | Path,
    *,
    run_id: str | None = None,
    clean: bool = False,
    progress: Callable[[str], None] | None = None,
) -> BatchManifest:
    """Split, validate, compile, and generate noiseless circuits for a batch of inputs.

    Args:
        inputs: A mix of ``.dae`` paths, ``.bgraph`` paths, and in-memory block graphs. Each is
            routed to the appropriate splitter and contributes its gadgets to one manifest.
        config: The scoring and generation parameters. ``config.conventions`` and ``config.ks``
            drive the compile/circuit loop, while ``config.logical_observables`` selects the
            logical correlation surfaces to compile. Open graphs derive compatible concrete
            port completions from that selection.
        output_dir: The run directory. Circuits land in ``output_dir/circuits`` and graphs in
            ``output_dir/graphs``; ``manifest.json`` is written at its root.
        run_id: A stable run id recorded in the manifest. Defaults to the output directory name.
        clean: When ``True``, remove pre-existing split DAE files before splitting.
        progress: An optional callback invoked with human-readable progress messages.

    Returns:
        A :class:`BatchManifest` describing every gadget built, including terminal
        records for gadgets that failed. Also written to ``output_dir/manifest.json``.

    """
    config.validate()

    run_dir = Path(output_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    circuits_dir = run_dir / "circuits"
    graphs_dir = run_dir / "graphs"

    def emit(message: str) -> None:
        if progress is not None:
            progress(message)

    units: list[ManifestUnit] = []
    for source_name, gadget_id, graph, error, error_type in _iter_gadgets(
        inputs, run_dir, clean=clean, emit=emit
    ):
        if graph is None:
            # Source-level import failure: one terminal unit standing in for the whole source.
            units.append(
                _import_failure_unit(
                    gadget_id,
                    source_name,
                    error or "import failed",
                    error_type or "ImportError",
                )
            )
            continue
        units.extend(
            _prepare_gadget(
                gadget_id,
                source_name,
                graph,
                config=config,
                circuits_dir=circuits_dir,
                graphs_dir=graphs_dir,
                run_dir=run_dir,
                emit=emit,
            )
        )

    _reject_duplicate_unit_keys(units)

    manifest = BatchManifest(
        run_id=run_id or run_dir.name,
        config=config,
        units=units,
        run_dir=run_dir,
    )
    manifest.write(run_dir)
    emit(f"Wrote manifest with {len(units)} unit(s)")
    return manifest


def _iter_gadgets(
    inputs: Sequence[str | Path | BlockGraph],
    run_dir: Path,
    *,
    clean: bool,
    emit: Callable[[str], None],
) -> list[_GadgetRow]:
    """Route every input to its splitter and yield ``(source, gadget_id, graph, error, type)`` rows.

    A ``graph`` of ``None`` marks a source-level import failure recorded as a single terminal
    unit, with ``error`` carrying the message and ``type`` the real exception type name. Only the
    narrow set of expected import/conversion errors is caught; interrupts and programming errors
    propagate.

    Each input's index in ``inputs`` is folded into the id namespace as an ``s{index:02d}_``
    prefix, so ids from two distinct inputs (for example two same-named ``model.dae`` files from
    different directories) can never collide.
    """
    gadgets: list[_GadgetRow] = []
    for index, item in enumerate(inputs):
        if isinstance(item, BlockGraph):
            source = "<in-memory>"
            stem = _namespaced(index, _slug(item.name) or "gadget")
            emit(f"Splitting in-memory graph {item.name!r}")
            gadgets.extend(_split_graph(item, source, stem))
            continue

        path = Path(item)
        suffix = path.suffix.lower()
        if suffix == ".dae":
            gadgets.extend(_split_dae(path, run_dir, index, clean=clean, emit=emit))
        elif suffix == ".bgraph":
            gadgets.extend(_split_bgraph(path, index, emit=emit))
        else:
            raise TQECError(
                f"Unsupported input {path.name!r}: expected a .dae, .bgraph, or BlockGraph."
            )
    return gadgets


def _namespaced(index: int, stem: str) -> str:
    """Prefix a stem with its input ordinal so ids from distinct inputs cannot collide."""
    return f"s{index:02d}_{stem}"


def _reject_duplicate_unit_keys(units: list[ManifestUnit]) -> None:
    """Fail fast if two units share a gadget/convention identity.

    Raises:
        TQECError: Naming the first colliding identity found.

    """
    seen: set[tuple[str, str]] = set()
    for unit in units:
        key = (unit.gadget_id, unit.convention)
        if key in seen:
            raise TQECError(
                f"Duplicate orchestration unit {key!r}: two components resolved to the same "
                "gadget and convention and would overwrite each other's artifacts."
            )
        seen.add(key)


def _split_dae(
    path: Path,
    run_dir: Path,
    index: int,
    *,
    clean: bool,
    emit: Callable[[str], None],
) -> list[_GadgetRow]:
    """Split a DAE into per-gadget graphs via the geometry-aware DAE splitter.

    The whole file is never imported at once (a single lattice offset cannot cancel several
    independent world-space translations); each component is written out and imported on its
    own. A discovery-time failure aborts the split and is recorded as one import failure for the
    source, consistent with the batch module's contract that discovery is not isolated.
    ``index`` is the input's ordinal, folded into every id to keep same-named files distinct.
    """
    from tqec.interop.batch import split_dae_batch  # noqa: PLC0415
    from tqec.interop.collada import read_block_graph_from_dae_file  # noqa: PLC0415

    source = path.name
    emit(f"Splitting DAE {source}")
    try:
        component_paths = split_dae_batch(path, run_dir / "gadgets", clean=clean)
    except _import_errors() as exc:
        emit(f"DAE split failed for {source}: {exc}")
        return [(source, _namespaced(index, path.stem), None, str(exc), type(exc).__name__)]

    gadgets: list[_GadgetRow] = []
    for component_path in component_paths:
        gadget_id = _namespaced(index, component_path.stem)
        try:
            graph = read_block_graph_from_dae_file(component_path, graph_name=gadget_id)
        except (*_import_errors(), ValueError) as exc:
            # A single component that will not import (a malformed block, or a
            # placeholder whose block-kind string is not a real cube) is recorded as one
            # terminal import failure and never aborts the rest of the batch. ``ValueError`` is
            # included because an unparseable block-kind string surfaces as one, not a TQECError.
            emit(f"Import failed for {gadget_id}: {exc}")
            gadgets.append((source, gadget_id, None, str(exc), type(exc).__name__))
            continue
        gadgets.append((source, gadget_id, graph, None, None))
    return gadgets


def _split_bgraph(
    path: Path,
    index: int,
    *,
    emit: Callable[[str], None],
) -> list[_GadgetRow]:
    """Read a BGRAPH and split it into connected components (it may hold several gadgets)."""
    source = path.name
    stem = _namespaced(index, path.stem)
    emit(f"Reading BGRAPH {source}")
    try:
        graph = read_bgraph(path, graph_name=path.stem)
    except _import_errors() as exc:
        emit(f"Import failed for {path.stem}: {exc}")
        return [(source, stem, None, str(exc), type(exc).__name__)]
    return _split_graph(graph, source, stem)


def _split_graph(
    graph: BlockGraph,
    source: str,
    stem: str,
) -> list[_GadgetRow]:
    """Split an imported graph into connected components, numbering them ``{stem}_batchNN``."""
    components = graph.split_block_graph_batch()
    if len(components) <= 1:
        return [(source, stem, graph, None, None)]
    from tqec.interop.batch import batch_member_stem  # noqa: PLC0415

    return [
        (source, batch_member_stem(stem, index), component, None, None)
        for index, component in enumerate(components, start=1)
    ]


def _prepare_gadget(
    gadget_id: str,
    source: str,
    graph: BlockGraph,
    *,
    config: BatchConfig,
    circuits_dir: Path,
    graphs_dir: Path,
    run_dir: Path,
    emit: Callable[[str], None],
) -> list[ManifestUnit]:
    """Generate circuits for one gadget, with one unit per filling and convention.

    Stops at the first failure with a terminal unit and an immediate ``FAILED [...]`` line on
    stderr; a failure in one gadget never stops the others. A component with nothing compilable
    (a pure open-port placeholder) is skipped rather than validated or compiled.
    """
    if _is_port_only(graph):
        emit(f"Skipping {gadget_id}: pure open-port placeholder (nothing to compile)")
        return [
            ManifestUnit(
                gadget_id=gadget_id,
                source=source,
                name=graph.name,
                convention="",
                status=UnitStatus.SKIPPED.value,
                notes="pure open-port placeholder; skipped",
            )
        ]

    try:
        graph.validate()
    except _EXPECTED_GADGET_ERRORS as exc:
        return [_fail(gadget_id, source, graph.name, UnitStatus.INVALID_GRAPH, "validate", exc)]

    original_graph_path = _save_graph(graph, graphs_dir, gadget_id, run_dir)

    try:
        fillings = _resolve_observable_fillings(gadget_id, graph, config)
    except _EXPECTED_GADGET_ERRORS as exc:
        unit = _fail(
            gadget_id,
            source,
            graph.name,
            UnitStatus.OBSERVABLE_FAILED,
            "observable",
            exc,
        )
        unit.graph = original_graph_path
        return [unit]

    units: list[ManifestUnit] = []
    for filling in fillings:
        # Persist the graph that is actually compiled. For open inputs this is the
        # completed graph, not the original graph containing Port placeholders.
        graph_path = _save_graph(filling.graph, graphs_dir, filling.gadget_id, run_dir)
        units.extend(
            [
                _compile_one(
                    filling.gadget_id,
                    source,
                    filling.graph,
                    observables=filling.observables,
                    convention=convention,
                    resolved_observables=filling.resolved_observables,
                    derived_port_cube_kinds=filling.derived_port_cube_kinds,
                    config=config,
                    circuits_dir=circuits_dir,
                    run_dir=run_dir,
                    graph_path=graph_path,
                    emit=emit,
                )
                for convention in config.conventions
            ]
        )
    return units


def _resolve_observable_fillings(
    base_id: str,
    graph: BlockGraph,
    config: BatchConfig,
) -> list[_ObservableFilling]:
    """Resolve the requested logical observables into compilation-ready gadgets."""
    selection = LogicalObservableSelection(config.logical_observables)
    if graph.num_ports == 0:
        observables = _select_logical_observables(graph, selection, config.random_seed)
        return [
            _ObservableFilling(
                gadget_id=base_id,
                graph=graph,
                observables=observables,
                resolved_observables=_describe_observables(graph, observables),
                derived_port_cube_kinds=None,
            )
        ]

    if selection is LogicalObservableSelection.AREA_MINIMIZED:
        filled_graphs = fill_ports_for_minimal_simulation(graph, search_small_area_observables=True)
    else:
        selected = _select_logical_observables(graph, selection, config.random_seed)
        filled_graphs = fill_ports_for_observables(graph, selected)

    fillings: list[_ObservableFilling] = []
    for filled in filled_graphs:
        port_cube_kinds = {
            port: str(filled.graph[graph.ports[port]].kind) for port in graph.ordered_ports
        }
        scheme_name = "__".join(
            f"{_slug(port)}-{_slug(kind)}" for port, kind in port_cube_kinds.items()
        )
        fillings.append(
            _ObservableFilling(
                gadget_id=f"{base_id}_ports_{scheme_name}",
                graph=filled.graph,
                observables=filled.observables,
                resolved_observables=tuple(
                    _describe_observable(stabilizer, observable)
                    for stabilizer, observable in zip(filled.stabilizers, filled.observables)
                ),
                derived_port_cube_kinds=port_cube_kinds,
            )
        )
    return fillings


def _select_logical_observables(
    graph: BlockGraph,
    selection: LogicalObservableSelection,
    random_seed: int | None,
) -> list[CorrelationSurface]:
    """Select correlation surfaces according to the user-facing mode."""
    generators = graph.find_correlation_surfaces()
    if not generators:
        raise TQECError("No logical observables were found on the block graph.")
    if selection is LogicalObservableSelection.ALL:
        return generators
    if selection is LogicalObservableSelection.RANDOM:
        return [random.Random(random_seed).choice(generators)]

    by_stabilizer = {
        observable.external_stabilizer_on_graph(graph): observable for observable in generators
    }
    if len(generators) > 16:
        warnings.warn(
            "Constructing every product of the logical-observable generators is "
            "exponential and may be slow.",
            TQECWarning,
        )
    for size in range(2, len(generators) + 1):
        for group in combinations(generators, size):
            observable = reduce(lambda left, right: left ^ right, group)
            stabilizer = observable.external_stabilizer_on_graph(graph)
            if set(stabilizer) != {"I"}:
                by_stabilizer.setdefault(stabilizer, observable)

    if selection is LogicalObservableSelection.ALL_POSSIBLE:
        return list(by_stabilizer.values())
    if selection is LogicalObservableSelection.AREA_MINIMIZED:
        minimized = reduce_observables_to_minimal_generators(by_stabilizer)
        return list(minimized.values())
    raise AssertionError(f"Unhandled logical-observable selection: {selection}")


def _describe_observables(
    graph: BlockGraph, observables: list[CorrelationSurface]
) -> tuple[ResolvedLogicalObservable, ...]:
    """Describe selected surfaces using their external stabilizers on ``graph``."""
    return tuple(
        _describe_observable(observable.external_stabilizer_on_graph(graph), observable)
        for observable in observables
    )


def _describe_observable(
    external_stabilizer: str, observable: CorrelationSurface
) -> ResolvedLogicalObservable:
    """Build stable manifest provenance for one correlation surface."""
    surface_id = hashlib.sha256(repr(sorted(observable.span, key=repr)).encode()).hexdigest()[:16]
    return ResolvedLogicalObservable(
        external_stabilizer=external_stabilizer,
        surface_id=surface_id,
        area=observable.area,
    )


def _compile_one(
    gadget_id: str,
    source: str,
    graph: BlockGraph,
    *,
    observables: list[CorrelationSurface],
    convention: str,
    resolved_observables: tuple[ResolvedLogicalObservable, ...],
    derived_port_cube_kinds: dict[str, str] | None,
    config: BatchConfig,
    circuits_dir: Path,
    run_dir: Path,
    graph_path: str | None,
    emit: Callable[[str], None],
) -> ManifestUnit:
    """Compile one filled graph under one convention and generate its noiseless circuits."""
    try:
        convention_obj = ALL_CONVENTIONS[convention]
    except KeyError as exc:
        raise TQECError(f"Unknown convention {convention!r}.") from exc

    observable_count = len(observables)

    emit(f"Compiling {gadget_id} [{convention}]")
    try:
        compiled = compile_block_graph(graph, convention_obj, observables=observables)
    except _EXPECTED_GADGET_ERRORS as exc:
        unit = _fail(gadget_id, source, graph.name, UnitStatus.COMPILE_FAILED, "compile", exc)
        unit.convention = convention
        unit.logical_observables = resolved_observables
        unit.derived_port_cube_kinds = derived_port_cube_kinds
        unit.observables = observable_count
        unit.graph = graph_path
        return unit

    suffix = _CONV_SUFFIX.get(convention, convention)
    circuits: dict[int, str] = {}
    failed_ks: list[int] = []
    last_exc: BaseException | None = None
    for k in config.ks:
        emit(f"Generating {gadget_id} [{convention}] k={k}")
        circuit_path = circuits_dir / f"{gadget_id}.{suffix}.k{k}.stim"
        circuit_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            write_circuit(
                compiled,
                k,
                circuit_path,
                mode=config.circuit_mode,
                manhattan_radius=config.manhattan_radius,
            )
        except _EXPECTED_GADGET_ERRORS as exc:
            # A single k failing does not doom the unit: keep the circuits that did generate.
            failed_ks.append(k)
            last_exc = exc
            _print_failure(gadget_id, "circuit", exc)
            continue
        circuits[k] = _relpath(circuit_path, run_dir)

    if not circuits:
        # No k produced a circuit: a terminal CIRCUIT_FAILED unit (each failing k already
        # printed its own FAILED [circuit] line above, so this does not reprint).
        return ManifestUnit(
            gadget_id=gadget_id,
            source=source,
            name=graph.name,
            convention=convention,
            status=UnitStatus.CIRCUIT_FAILED.value,
            logical_observables=resolved_observables,
            derived_port_cube_kinds=derived_port_cube_kinds,
            observables=observable_count,
            graph=graph_path,
            notes=str(last_exc) if last_exc is not None else "",
            stage="circuit",
            error=type(last_exc).__name__ if last_exc is not None else "",
        )

    notes = ""
    if failed_ks:
        ks_text = ", ".join(f"k={k}" for k in failed_ks)
        notes = f"circuit generation failed for {ks_text}: {last_exc}"
    return ManifestUnit(
        gadget_id=gadget_id,
        source=source,
        name=graph.name,
        convention=convention,
        status=UnitStatus.READY.value,
        logical_observables=resolved_observables,
        derived_port_cube_kinds=derived_port_cube_kinds,
        observables=observable_count,
        circuits=circuits,
        graph=graph_path,
        notes=notes,
    )


def _is_port_only(graph: BlockGraph) -> bool:
    """Return whether a graph has no compilable content (only ``Port`` placeholders, or nothing).

    A component that is nothing but open-port cubes has no code patch to compile; a normal
    primitive with open ports still has non-port cubes and is not skipped (its ports get filled).
    """
    return not any(not cube.is_port for cube in graph.cubes)


def _save_graph(graph: BlockGraph, graphs_dir: Path, gadget_id: str, run_dir: Path) -> str | None:
    """Write the gadget's block graph JSON and return its run-relative path (or ``None``)."""
    graphs_dir.mkdir(parents=True, exist_ok=True)
    json_path = graphs_dir / f"{gadget_id}.json"
    try:
        graph.to_json(json_path)
    except _EXPECTED_GADGET_ERRORS:
        return None
    return _relpath(json_path, run_dir)


def _print_failure(gadget_id: str, stage: str, exc: BaseException) -> None:
    """Print a ``FAILED [stage] ...`` line for one gadget failure to stderr."""
    print(
        str(BatchFailure(gadget_id, stage, type(exc).__name__, str(exc))),
        file=sys.stderr,
    )


def _fail(
    gadget_id: str,
    source: str,
    name: str,
    status: UnitStatus,
    stage: str,
    exc: BaseException,
) -> ManifestUnit:
    """Build a terminal unit for a failed gadget and print its failure line to stderr."""
    _print_failure(gadget_id, stage, exc)
    return ManifestUnit(
        gadget_id=gadget_id,
        source=source,
        name=name,
        convention="",
        status=status.value,
        notes=str(exc),
        stage=stage,
        error=type(exc).__name__,
    )


def _import_failure_unit(
    gadget_id: str, source: str, message: str, error_type: str
) -> ManifestUnit:
    """Build the terminal unit for a source-level import failure and report it to stderr.

    ``error_type`` is the real exception type name captured at the catch site, so the true error
    (a ``DaeError``, a ``TQECError``, ...) survives rather than a hardcoded ``ImportError``.
    """
    failure = BatchFailure(gadget_id, "import", error_type, message)
    print(str(failure), file=sys.stderr)
    return ManifestUnit(
        gadget_id=gadget_id,
        source=source,
        name="",
        convention="",
        status=UnitStatus.IMPORT_FAILED.value,
        notes=message,
        stage="import",
        error=error_type,
    )


def _relpath(path: Path, run_dir: Path) -> str:
    """Return ``path`` relative to ``run_dir``."""
    return os.path.relpath(path, run_dir)


def _slug(name: str) -> str:
    """Return a filesystem-safe slug of a graph name."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.lower()).strip("_")
    return slug[:40]


def _import_errors() -> tuple[type[BaseException], ...]:
    """Return the expected import/conversion errors, including collada's, imported lazily."""
    import collada  # noqa: PLC0415

    return (TQECError, collada.DaeError)
