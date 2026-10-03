from typing import Final

EXTENDED_PLAQUETTE_SCHEDULES: Final[dict[bool, dict[bool, tuple[int, int, int, int]]]] = {
    # Flipping-style schedules along the vertical axis of the plaquettes.
    True: {
        False: (2, 4, 3, 5),
        True: (4, 2, 5, 3),
    },
    # Legacy schedules with complete time-reversal.
    False: {
        False: (2, 4, 3, 5),
        True: (5, 3, 4, 2),
    },
}
VERTICAL_HOOK_SCHEDULES: Final[dict[bool, dict[bool, tuple[int, int, int, int]]]] = {
    # Flipping-style schedules along the vertical axis of the plaquettes.
    True: {
        False: (1, 4, 3, 5),
        True: (4, 1, 5, 3),
    },
    # Legacy schedules with complete time-reversal.
    False: {
        False: (1, 4, 3, 5),
        True: (5, 3, 4, 1),
    },
}
HORIZONTAL_HOOK_SCHEDULES: Final[dict[bool, dict[bool, tuple[int, int, int, int]]]] = {
    # Flipping-style schedules along the vertical axis of the plaquettes.
    True: {
        False: (1, 2, 3, 5),
        True: (2, 1, 5, 3),
    },
    # Legacy schedules with complete time-reversal.
    False: {
        False: (1, 2, 3, 5),
        True: (5, 3, 2, 1),
    },
}
