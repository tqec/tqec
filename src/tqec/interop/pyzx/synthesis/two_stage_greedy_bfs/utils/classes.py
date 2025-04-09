from dataclasses import dataclass
from typing import Tuple, List
from tqec.interop.pyzx.synthesis.two_stage_greedy_bfs.two_stage_greedy_bfs_config import (
    VALUE_HYPERPARAMS,
)


# MAIN DATA CLASS TO STORE PATHS AND ENABLE COMPARISONS
@dataclass(order=True)
class Path:
    target_pos: Tuple[int, int, int]
    target_kind: str
    target_beams: List[Tuple[int, int, int]]
    coords_in_path: List[Tuple[int, int, int]]
    all_nodes_in_path: List[Tuple[Tuple[int, int, int], str]]
    beams_broken_by_path: int
    len_of_path: int
    target_unobstructed_exits_n: int

    def weighed_value(self, stage) -> int:
        path_len_hp, beams_broken_hp, target_exits_hp = VALUE_HYPERPARAMS
        return (
            self.len_of_path * path_len_hp
            + self.beams_broken_by_path * beams_broken_hp
            + self.target_unobstructed_exits_n * target_exits_hp
        )
