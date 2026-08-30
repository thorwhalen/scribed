"""Tests for the CLI surface (the ``[cli]`` extra, dispatched by ``cw``).

``import scribed`` is dependency-free by design and the CLI dependency lives in an
extra, so there are two things to hold still here: the parser must build a help page
for every dispatched tool, and the entry point must explain itself — rather than
traceback — when the extra is not installed.
"""

import importlib.util
import os
import subprocess
import sys

import pytest

from scribed import tools

HAS_CW = importlib.util.find_spec("cw") is not None


def test_dispatch_funcs_is_sound():
    # The SSOT list the CLI dispatches must be all callables with docstrings.
    assert tools._dispatch_funcs
    for f in tools._dispatch_funcs:
        assert callable(f) and (f.__doc__ or "").strip(), f.__name__


@pytest.mark.skipif(not HAS_CW, reason="cw (cli extra) not installed")
def test_python_m_scribed_runs():
    out = subprocess.run(
        [sys.executable, "-m", "scribed", "backends"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert out.returncode == 0, out.stderr
    assert "faster-whisper" in out.stdout


@pytest.mark.skipif(not HAS_CW, reason="cw (cli extra) not installed")
def test_top_level_help_lists_every_command():
    out = subprocess.run(
        [sys.executable, "-m", "scribed", "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert out.returncode == 0, out.stderr
    for f in tools._dispatch_funcs:
        assert f.__name__ in out.stdout


@pytest.mark.skipif(not HAS_CW, reason="cw (cli extra) not installed")
@pytest.mark.parametrize("command", [f.__name__ for f in tools._dispatch_funcs])
def test_every_subcommand_has_help(command):
    """``scribed <command> --help`` must build and render for every dispatched tool."""
    out = subprocess.run(
        [sys.executable, "-m", "scribed", command, "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert out.returncode == 0, out.stderr
    assert f"{command} [-h]" in out.stdout


@pytest.mark.skipif(not HAS_CW, reason="cw (cli extra) not installed")
def test_usage_error_exits_two():
    out = subprocess.run(
        [sys.executable, "-m", "scribed", "transcribe"],  # missing required positional
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert out.returncode == 2
    assert "usage:" in out.stderr


def test_friendly_error_when_cli_extra_missing(tmp_path):
    """Without the ``[cli]`` extra the CLI must explain itself, not traceback.

    Masking the dependency with a module that raises ImportError is the portable way
    to exercise that branch without uninstalling anything.
    """
    (tmp_path / "cw.py").write_text("raise ImportError('masked for test')\n")
    env = dict(os.environ, PYTHONPATH=str(tmp_path))
    out = subprocess.run(
        [sys.executable, "-m", "scribed", "backends"],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert out.returncode == 1
    assert "The scribed CLI requires 'cw'" in out.stderr
    assert "pip install 'scribed[cli]'" in out.stderr
    assert "Traceback" not in out.stderr
