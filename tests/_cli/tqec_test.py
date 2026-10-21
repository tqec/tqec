import argparse
import logging

import pytest

from tqec._cli import tqec
from tqec.compile.compile import compile_block_graph
from tqec.gallery.cnot import cnot
from tqec.utils.enums import Basis


def _compile_only(args: argparse.Namespace) -> None:
    # Stands in for run-example so that no simulation runs; compiling the CNOT
    # example logs from tqec.compile.compile at DEBUG level.
    compile_block_graph(cnot(Basis.Z))


def test_log_level_defaults_to_warning() -> None:
    args = tqec._build_parser().parse_args(["run-example", "--out-dir", "out"])
    assert args.log_level == "WARNING"


def test_log_level_is_case_insensitive() -> None:
    args = tqec._build_parser().parse_args(
        ["--log-level", "debug", "run-example", "--out-dir", "out"]
    )
    assert args.log_level == "DEBUG"


def test_unknown_log_level_is_rejected() -> None:
    with pytest.raises(SystemExit):
        tqec._build_parser().parse_args(
            ["--log-level", "verbose", "run-example", "--out-dir", "out"]
        )


def test_main_shows_compile_debug_logs_with_log_level_debug(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(tqec.RunExampleTQECSubCommand, "execute", staticmethod(_compile_only))
    monkeypatch.setattr(
        "sys.argv", ["tqec", "--log-level", "DEBUG", "run-example", "--out-dir", "out"]
    )
    root = logging.getLogger()
    monkeypatch.setattr(root, "level", logging.WARNING)  # restored after the test
    tqec.main()
    assert root.level == logging.DEBUG
    assert any(r.name == "tqec.compile.compile" for r in caplog.records)


def test_main_hides_compile_debug_logs_by_default(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(tqec.RunExampleTQECSubCommand, "execute", staticmethod(_compile_only))
    monkeypatch.setattr("sys.argv", ["tqec", "run-example", "--out-dir", "out"])
    root = logging.getLogger()
    monkeypatch.setattr(root, "level", logging.DEBUG)  # restored after the test
    tqec.main()
    assert root.level == logging.WARNING
    assert not [r for r in caplog.records if r.name == "tqec.compile.compile"]
