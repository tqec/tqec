from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Convention:
    """Represent a convention to implement blocks."""

    name: str

    def __str__(self) -> str:
        return self.name  # pragma: no cover


FIXED_BULK_CONVENTION = Convention("fixed_bulk")
FIXED_BOUNDARY_CONVENTION = Convention("fixed_boundary")

ALL_CONVENTIONS = {
    conv.name: conv
    for conv in [
        FIXED_BULK_CONVENTION,
        FIXED_BOUNDARY_CONVENTION,
    ]
}
