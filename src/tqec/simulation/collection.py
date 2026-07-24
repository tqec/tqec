"""Shared ``sinter.collect`` option adapter for the tqec simulation entry points.

Both :func:`tqec.simulation.simulation.start_simulation_using_sinter` and
:func:`tqec.orchestration.simulate.simulate_batch` end in a call to :func:`sinter.collect`, and
both assemble the same family of collection knobs--worker count, stopping conditions
(``max_shots`` / ``max_errors``), batching limits, decoders, resume/existing-data files, the
progress callback, custom decoders, ``print_progress`` and ``hint_num_tasks``. Only that option
mapping is shared here; task construction, circuit generation and detector annotation stay with
each caller.

:class:`CollectionOptions` centralizes the normalization (path coercion, iterable/mapping
copying, ``None`` handling) so both call sites feed ``sinter.collect`` a consistent kwargs
mapping. Each caller merges the mapping from :meth:`CollectionOptions.to_collect_kwargs` with its
own ``tasks`` and any call-specific extras (for example ``count_observable_error_combos``).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import sinter


@dataclass(frozen=True)
class CollectionOptions:
    """The collection knobs common to every tqec ``sinter.collect`` call site.

    This deliberately excludes ``tasks`` (each caller builds its own task iterable) and any
    caller-specific options such as ``count_observable_error_combos`` /
    ``custom_error_count_key``; those are passed alongside the mapping this produces.
    """

    num_workers: int
    max_shots: int | None = None
    max_errors: int | None = None
    max_batch_size: int | None = None
    max_batch_seconds: int | None = None
    decoders: Iterable[str] = ("pymatching",)
    existing_data_filepaths: Iterable[str | Path] = ()
    save_resume_filepath: str | Path | None = None
    progress_callback: Callable[[sinter.Progress], None] | None = None
    custom_decoders: Mapping[str, sinter.Decoder | sinter.Sampler] | None = None
    print_progress: bool = False
    hint_num_tasks: int | None = None

    def to_collect_kwargs(self) -> dict[str, Any]:
        """Return the normalized keyword arguments to pass to :func:`sinter.collect`.

        Paths are coerced to :class:`~pathlib.Path`, iterables/mappings are copied so the caller's
        inputs are not aliased, and ``None`` values are preserved (they match ``sinter.collect``'s
        own defaults). The result never contains ``tasks``--the caller supplies that.
        """
        return {
            "num_workers": self.num_workers,
            "max_shots": self.max_shots,
            "max_errors": self.max_errors,
            "max_batch_size": self.max_batch_size,
            "max_batch_seconds": self.max_batch_seconds,
            "decoders": list(self.decoders),
            "existing_data_filepaths": [Path(p) for p in self.existing_data_filepaths],
            "save_resume_filepath": (
                None
                if self.save_resume_filepath is None
                else Path(self.save_resume_filepath)
            ),
            "progress_callback": self.progress_callback,
            "custom_decoders": dict(self.custom_decoders)
            if self.custom_decoders
            else None,
            "print_progress": self.print_progress,
            "hint_num_tasks": self.hint_num_tasks,
        }
