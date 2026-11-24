"""Check that passing only ``database_path`` creates and then reuses the detector database."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tqec.compile.compile import compile_block_graph
from tqec.compile.detectors.database import DetectorDatabase
from tqec.gallery.memory import memory
from tqec.utils.exceptions import TQECError


def _circuit(database_path: Path | None) -> str:
    compiled = compile_block_graph(memory())
    return str(compiled.generate_stim_circuit(1, manhattan_radius=1, database_path=database_path))


def test_path_only_creates_database_file(tmp_path: Path) -> None:
    path = tmp_path / "db.pkl"
    assert not path.exists()
    _circuit(path)
    assert path.exists()
    assert len(DetectorDatabase.from_file(path)) > 0


def test_path_only_second_call_reuses_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "db.pkl"
    first = _circuit(path)
    size = len(DetectorDatabase.from_file(path))

    # Any recomputation would try to add a situation, which now raises.
    def _no_add(self: DetectorDatabase, *args: object, **kwargs: object) -> None:
        raise TQECError("detectors were recomputed instead of read from the database")

    monkeypatch.setattr(DetectorDatabase, "add_situation", _no_add)
    second = _circuit(path)
    assert second == first
    assert len(DetectorDatabase.from_file(path)) == size


def test_default_path_creates_database_file(tmp_path: Path) -> None:
    default = tmp_path / "default.pkl"
    code = textwrap.dedent(
        """
        from tqec.compile.compile import compile_block_graph
        from tqec.gallery.memory import memory

        compile_block_graph(memory()).generate_stim_circuit(1, manhattan_radius=1)
        """
    )
    env = {**os.environ, "TQEC_DETECTOR_DATABASE_PATH": str(default)}
    subprocess.run([sys.executable, "-c", code], env=env, check=True, timeout=25)
    assert default.exists()
    assert len(DetectorDatabase.from_file(default)) > 0
