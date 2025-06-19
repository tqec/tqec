from typing import Final

EXTENDED_PLAQUETTE_SCHEDULES: Final[dict[bool, tuple[int, int, int, int]]] = {
    False: (2, 4, 3, 5),
    True: (5, 3, 4, 2),
}
VERTICAL_HOOK_SCHEDULES: Final[dict[bool, tuple[int, int, int, int]]] = {
    False: (1, 4, 3, 5),
    True: (5, 3, 4, 1),
}
HORIZONTAL_HOOK_SCHEDULES: Final[dict[bool, tuple[int, int, int, int]]] = {
    False: (1, 2, 3, 5),
    True: (5, 3, 2, 1),
}
