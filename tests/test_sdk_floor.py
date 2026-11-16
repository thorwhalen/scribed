"""An SDK older than a backend's declared floor is not reported as available."""

import importlib.metadata as metadata
import re
import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("packaging")

import scribed
from scribed import registry


@pytest.fixture(autouse=True)
def fresh_cache():
    registry.sdk_problem.cache_clear()
    yield
    registry.sdk_problem.cache_clear()


@pytest.fixture
def fake_groq(monkeypatch):
    monkeypatch.setitem(sys.modules, "groq", types.ModuleType("groq"))


def _installed(monkeypatch, version):
    monkeypatch.setattr(metadata, "version", lambda name: version)


def test_old_sdk_is_not_available_and_says_why(monkeypatch, fake_groq):
    _installed(monkeypatch, "0.11.0")
    assert registry._is_available("groq") is False
    assert "groq>=0.20.0" in registry.sdk_problem("groq")
    assert "groq>=0.20.0" in scribed.doctor()["missing"]["groq"]


def test_sdk_at_the_floor_is_available(monkeypatch, fake_groq):
    _installed(monkeypatch, "0.20.0")
    assert registry._is_available("groq") is True


def test_prerelease_below_the_floor_is_too_old(monkeypatch, fake_groq):
    _installed(monkeypatch, "0.20.0rc1")
    assert registry._is_available("groq") is False


def test_unverifiable_floor_never_blocks(monkeypatch, fake_groq):
    def boom(name):
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(metadata, "version", boom)
    assert registry._is_available("groq") is True


def test_backend_without_a_floor_is_untouched():
    assert registry.sdk_problem("vosk") is None


def test_elevenlabs_broken_releases_are_excluded(monkeypatch):
    monkeypatch.setitem(sys.modules, "elevenlabs", types.ModuleType("elevenlabs"))
    for version, ok in [
        ("1.50.0", False),
        ("1.57.0", True),
        ("2.19.0", False),
        ("2.20.0", False),
        ("2.20.1", True),
        ("2.45.0", True),
    ]:
        registry.sdk_problem.cache_clear()
        _installed(monkeypatch, version)
        assert (registry.sdk_problem("elevenlabs") is None) is ok, version


def test_install_upgrades_only_the_sdk_when_it_is_too_old(monkeypatch, fake_groq):
    import subprocess

    from scribed.install import install

    _installed(monkeypatch, "0.11.0")
    ran = []
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **k: (
            ran.append(cmd) or types.SimpleNamespace(returncode=0, stdout="", stderr="")
        ),
    )
    install("groq", yes=True, verify=False)
    assert ran[0][-3:] == ["install", "--upgrade", "groq>=0.20.0"]


def _pyproject_extras():
    try:
        import tomllib
    except ImportError:  # Python 3.10
        tomllib = pytest.importorskip("tomli")
    path = Path(__file__).parent.parent / "pyproject.toml"
    return tomllib.loads(path.read_text())["project"]["optional-dependencies"]


def test_declared_requirements_match_pyproject_extras():
    from packaging.requirements import Requirement

    from scribed.install import requirements

    extras = _pyproject_extras()
    checked = 0
    for backend_id in scribed.list_backends():
        spec = scribed.get_config(backend_id).get("sdk_requirement")
        if not spec:
            continue
        want = Requirement(spec)
        extra = requirements(backend_id).extra
        in_extra = [Requirement(r) for r in extras[extra]]
        (got,) = [r for r in in_extra if r.name == want.name]
        assert got.specifier == want.specifier, backend_id
        checked += 1
    assert checked >= 3
