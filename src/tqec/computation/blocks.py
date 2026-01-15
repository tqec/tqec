"""Defines additional block types beyond cubes and pipes."""

from __future__ import annotations


class PatchRotation:
    """Block type representing a patch rotation.

    Note: Implementation is not yet complete. See issue #571 for details.
    """

    def __str__(self) -> str:
        return "PATCH_ROTATION"

    def __hash__(self) -> int:
        return hash(PatchRotation)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, PatchRotation)


class Cultivation:
    """Block type representing magic state cultivation.

    Note: Implementation is not yet complete. See issue #571 for details.
    """

    def __str__(self) -> str:
        return "CULTIVATION"

    def __hash__(self) -> int:
        return hash(Cultivation)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Cultivation)