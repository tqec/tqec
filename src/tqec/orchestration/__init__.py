"""Batch orchestration for tqec: prepare gadgets into circuits, then sample them.

The package splits a batch of inputs (``.dae`` / ``.bgraph`` files and in-memory block graphs)
into gadgets, compiles each gadget into noiseless circuits (:func:`prepare_batch`, writing
``manifest.json``), and then applies noise and runs a single flattened :func:`sinter.collect`
over the whole batch (:func:`simulate_batch`, writing ``results.json``).

The two stages communicate only through run-directory files, so they can run as separate jobs.
:mod:`tqec.orchestration.schema` and :mod:`tqec.orchestration.prepare` import neither
:mod:`sinter`
nor :mod:`collada`, so a scheduler can prepare or inspect a manifest without them. ``sinter`` is
confined to :mod:`tqec.orchestration.simulate`, which this package imports lazily: accessing
:func:`simulate_batch` is what pulls it in, so ``import tqec.orchestration`` alone stays
sinter-free.
"""

from typing import TYPE_CHECKING, Any

from tqec.orchestration.prepare import prepare_batch as prepare_batch
from tqec.orchestration.schema import (
    AggregateStatus as AggregateStatus,
)
from tqec.orchestration.schema import (
    BatchConfig as BatchConfig,
)
from tqec.orchestration.schema import (
    BatchFailure as BatchFailure,
)
from tqec.orchestration.schema import (
    BatchManifest as BatchManifest,
)
from tqec.orchestration.schema import (
    BatchResult as BatchResult,
)
from tqec.orchestration.schema import (
    LogicalObservableSelection as LogicalObservableSelection,
)
from tqec.orchestration.schema import (
    ManifestUnit as ManifestUnit,
)
from tqec.orchestration.schema import (
    ResolvedLogicalObservable as ResolvedLogicalObservable,
)
from tqec.orchestration.schema import (
    UnitResult as UnitResult,
)
from tqec.orchestration.schema import (
    UnitStatus as UnitStatus,
)

if TYPE_CHECKING:
    from tqec.orchestration.simulate import simulate_batch as simulate_batch

__all__ = [
    "AggregateStatus",
    "BatchConfig",
    "BatchFailure",
    "BatchManifest",
    "BatchResult",
    "LogicalObservableSelection",
    "ManifestUnit",
    "ResolvedLogicalObservable",
    "UnitResult",
    "UnitStatus",
    "prepare_batch",
    "simulate_batch",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve :func:`simulate_batch` so importing the package stays sinter-free."""
    if name == "simulate_batch":
        from tqec.orchestration.simulate import simulate_batch  # noqa: PLC0415

        return simulate_batch
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
