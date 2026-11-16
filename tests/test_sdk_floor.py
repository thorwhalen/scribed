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


def test_declared_floors_match_pyproject():
    """Each config's min_sdk_version is the floor of its extra in pyproject.toml."""
    text = (Path(__file__).parent.parent / "pyproject.toml").read_text()
    checked = 0
    for backend_id in scribed.list_backends():
        config = scribed.get_config(backend_id)
        floor = config.get("min_sdk_version")
        if not floor:
            continue
        dist = config["pip_install"]
        found = re.search(rf'"{re.escape(dist)}>=([\d.]+)', text)
        assert found, f"no >= floor for {dist} in pyproject.toml"
        assert found.group(1) == floor, backend_id
        checked += 1
    assert checked >= 3
