"""An SDK older than the extra's floor is not reported as available."""

import importlib.metadata as metadata
import sys
import types

import pytest

pytest.importorskip("packaging")

from scribed import registry


@pytest.fixture
def fake_groq(monkeypatch):
    monkeypatch.setitem(sys.modules, "groq", types.ModuleType("groq"))
    monkeypatch.setattr(
        metadata,
        "requires",
        lambda name: ["groq>=0.20.0; extra == 'groq'", "ocracy>=0.1"],
    )


def _installed(monkeypatch, version):
    monkeypatch.setattr(metadata, "version", lambda name: version)


def test_old_sdk_is_not_available(monkeypatch, fake_groq):
    _installed(monkeypatch, "0.11.0")
    assert registry._is_available("groq") is False


def test_sdk_at_the_floor_is_available(monkeypatch, fake_groq):
    _installed(monkeypatch, "0.20.0")
    assert registry._is_available("groq") is True


def test_unverifiable_floor_never_blocks(monkeypatch, fake_groq):
    def boom(name):
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(metadata, "version", boom)
    assert registry._is_available("groq") is True


def test_requirements_of_other_extras_are_ignored(monkeypatch, fake_groq):
    monkeypatch.setattr(
        metadata, "requires", lambda name: ["groq>=9; extra == 'something-else'"]
    )
    _installed(monkeypatch, "0.11.0")
    assert registry._is_available("groq") is True
