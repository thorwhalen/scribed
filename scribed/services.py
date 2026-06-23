"""Service layer: three tiers of access to backends.

- :class:`ServiceCollection` — a lazy mapping ``backend_id -> ServiceHandle``,
  also reachable by attribute (``services.faster_whisper``).
- :class:`ServiceHandle` — a per-backend namespace exposing the normalized
  ``transcribe`` method, the backend's ``config``/``info``, and the raw
  ``adapter``.

This gives three escalating levels of control::

    scribed.transcribe(audio)                            # 1. simple facade (default)
    scribed.services.deepgram.transcribe(audio, diarize=True)  # 2. pick a backend
    scribed.services.deepgram.adapter                    # 3. raw engine adapter

Mirrors the sibling ``ocracy`` facade's service layer.
"""

from __future__ import annotations

import functools
from collections.abc import Mapping
from typing import Any

from scribed import registry


class ServiceHandle:
    """Per-backend access point: normalized ``transcribe`` + native ``adapter``."""

    def __init__(self, backend_id: str):
        self._id = backend_id

    @property
    def name(self) -> str:
        return self._id

    @functools.cached_property
    def config(self) -> dict:
        return registry.get_config(self._id)

    @functools.cached_property
    def adapter(self) -> Any:
        return registry.get_backend(self._id)["adapter"]

    @functools.cached_property
    def info(self) -> dict:
        """Lightweight summary of the backend (no adapter load)."""
        c = self.config
        return {
            "id": c.get("id", c.get("name")),
            "name": c.get("display_name", c.get("name")),
            "capabilities": [registry.PRIMARY_CAPABILITY, *c.get("capabilities", [])],
            "license": c.get("license", "unknown"),
            "pip_install": c.get("pip_install", ""),
        }

    def transcribe(self, audio, **kwargs):
        """Transcribe ``audio`` with this backend. Returns a ``Transcript``."""
        return self.adapter.transcribe(audio, **kwargs)

    def __getattr__(self, name: str):
        """Proxy unknown attributes to the adapter (backend-specific methods)."""
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return getattr(self.adapter, name)
        except AttributeError:
            raise AttributeError(f"Backend {self._id!r} has no attribute {name!r}")

    def __repr__(self) -> str:
        caps = self.config.get("capabilities", [])
        return f"<ServiceHandle {self._id!r} capabilities={caps}>"


class ServiceCollection(Mapping):
    """Lazy mapping of backend ids -> :class:`ServiceHandle`.

    Supports dict-style (``services['deepgram']``) and attribute-style
    (``services.deepgram``) access.
    """

    def __init__(self):
        self._handles: dict = {}

    def _ensure(self):
        registry._discover_backends()

    def __getitem__(self, backend_id: str) -> ServiceHandle:
        self._ensure()
        if backend_id not in registry._registry:
            raise KeyError(
                f"Unknown backend: {backend_id!r}. "
                f"Available: {sorted(registry._registry)}"
            )
        if backend_id not in self._handles:
            self._handles[backend_id] = ServiceHandle(backend_id)
        return self._handles[backend_id]

    def __getattr__(self, name: str) -> ServiceHandle:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self[name]
        except KeyError:
            raise AttributeError(
                f"No backend named {name!r}. Available: {sorted(registry.list_backends())}"
            )

    def __iter__(self):
        self._ensure()
        return iter(sorted(registry._registry))

    def __len__(self):
        self._ensure()
        return len(registry._registry)

    def __contains__(self, name):
        self._ensure()
        return name in registry._registry

    def __repr__(self):
        return f"<ServiceCollection backends={list(self)}>"
