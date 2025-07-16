"""Defines the base :class:`Exception` and :class:`Warning` subclasses used by
the ``tqec`` library.
"""


class TQECError(Exception):
    pass


class TQECWarning(Warning):
    pass
