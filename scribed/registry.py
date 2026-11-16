"""Backend discovery, registration, and lazy loading.

An *implemented* backend is a subpackage of :mod:`scribed.backends` that ships
two things:

- ``config.py`` defining a ``BACKEND_CONFIG`` dict (id, pip_install, capabilities,
  ``param_map``, ...), and
- ``adapter.py`` defining an ``Adapter`` class whose ``transcribe(audio, **kwargs)``
  returns a :class:`scribed.base.Transcript`.

This registry scans for those at first use, loads each adapter *lazily* (so
importing scribed never imports heavy engine SDKs), and raises a friendly
``pip install`` error if a backend's dependency is missing. Third parties can
register their own backends at runtime via :func:`register_backend`.

The design mirrors the sibling ``ocracy`` facade, adapted for ASR: the primary
capability is ``"transcribe"`` (audio -> text+timing), with optional extra
capabilities (``"diarize"``, ``"stream"``, ``"translate"``, ...) declared per
backend. ``"whisper_sized_model"`` marks backends whose
``model`` accepts a bare Whisper size (``small``, ``large-v3``), so consumers can
derive that set with ``list_backends("whisper_sized_model")`` rather than hardcode it.
"""

from __future__ import annotations

import importlib
import pkgutil
import warnings
from typing import Any, Dict, List, Optional

# Module-level registry: backend_id -> {config, adapter (lazy), module_path}
_registry: Dict[str, Dict[str, Any]] = {}
_discovered = False

#: The capability every general ASR backend provides.
PRIMARY_CAPABILITY = "transcribe"


def _discover_backends() -> None:
    """Scan ``scribed.backends.*`` for ``BACKEND_CONFIG`` dicts (runs once)."""
    global _discovered
    if _discovered:
        return
    _discovered = True

    try:
        import scribed.backends as backends_pkg
    except ImportError:  # pragma: no cover
        return

    for _importer, modname, ispkg in pkgutil.iter_modules(
        backends_pkg.__path__, prefix="scribed.backends."
    ):
        if not ispkg:
            continue
        leaf = modname.rsplit(".", 1)[-1]
        if leaf.startswith("_"):  # _template and friends are not real backends
            continue
        try:
            config_mod = importlib.import_module(f"{modname}.config")
            config = getattr(config_mod, "BACKEND_CONFIG", None)
            if config is None:
                continue
            backend_id = config.get("id") or config["name"]
            _registry[backend_id] = {
                "config": config,
                "adapter": None,  # lazy
                "module_path": modname,
            }
        except Exception as e:  # pragma: no cover - defensive
            warnings.warn(
                f"Failed to load backend config from {modname}: {e}", stacklevel=2
            )


def _load_adapter(backend_id: str):
    """Lazily import + instantiate a backend's ``Adapter`` (friendly ImportError)."""
    entry = _registry.get(backend_id)
    if entry is None:
        raise KeyError(f"Unknown backend: {backend_id!r}")
    if entry["adapter"] is not None:
        return entry["adapter"]

    module_path = entry["module_path"]
    config = entry["config"]
    try:
        adapter_mod = importlib.import_module(f"{module_path}.adapter")
        adapter_cls = getattr(adapter_mod, "Adapter")
        entry["adapter"] = adapter_cls(config)
    except ImportError as e:
        pip_install = config.get("pip_install", backend_id)
        raise ImportError(
            f"Backend {backend_id!r} requires: pip install {pip_install}\n"
            f"Full install guidance (the scribed extra, system deps, GPU, weights): "
            f"scribed.requirements({backend_id!r}).instructions()  "
            f"or: scribed install {backend_id}\n"
            f"Original error: {e}"
        ) from e
    return entry["adapter"]


def _is_available(backend_id: str) -> bool:
    """Cheap probe: can this backend's primary dependency be imported?

    Uses ``import_name`` from the config without instantiating the adapter, so it
    is safe to call for every backend during default selection.
    """
    _discover_backends()
    entry = _registry.get(backend_id)
    if entry is None:
        return False
    import_name = entry["config"].get("import_name")
    if not import_name:
        # No declared import probe: assume available and let usage surface errors.
        return True
    try:
        importlib.import_module(import_name)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def register_backend(backend_id: str, config: dict, adapter: Any = None) -> None:
    """Register a backend at runtime (for third-party plugins).

    Args:
        backend_id: Unique identifier.
        config: ``BACKEND_CONFIG``-shaped dict (needs at least ``name``). Set
            ``is_local: True`` for a backend that never uploads audio: without it
            the backend is never chosen as an implicit default.
        adapter: Optional pre-instantiated adapter; else loaded lazily from
            ``config['module_path']`` when first used.
    """
    _discover_backends()
    _registry[backend_id] = {
        "config": config,
        "adapter": adapter,
        "module_path": config.get("module_path", ""),
    }


def list_backends(capability: Optional[str] = None) -> List[str]:
    """Sorted ids of implemented backends, optionally filtered by capability.

    A backend matches ``capability`` if it appears in the backend's
    ``capabilities`` list (the primary ``"transcribe"`` is implied for all).
    """
    _discover_backends()
    if capability is None:
        return sorted(_registry)
    return sorted(
        bid
        for bid, entry in _registry.items()
        if capability == PRIMARY_CAPABILITY
        or capability in entry["config"].get("capabilities", [])
    )


def get_config(backend_id: str) -> dict:
    """A backend's ``BACKEND_CONFIG`` without loading its adapter."""
    _discover_backends()
    if backend_id not in _registry:
        raise KeyError(
            f"Unknown backend: {backend_id!r}. Available: {sorted(_registry)}"
        )
    return _registry[backend_id]["config"]


def get_backend(backend_id: str) -> dict:
    """Config + lazily-loaded adapter for a backend (raises on missing deps)."""
    _discover_backends()
    if backend_id not in _registry:
        raise KeyError(
            f"Unknown backend: {backend_id!r}. Available: {sorted(_registry)}"
        )
    return {
        "config": _registry[backend_id]["config"],
        "adapter": _load_adapter(backend_id),
    }


def is_local(backend_id: str) -> bool:
    """Does ``backend_id`` run entirely on this machine (never uploads audio)?

    A config lacking ``is_local`` (e.g. a third-party plugin that does not say) or
    flagged ``is_remote`` counts as *not* local: the safe reading.
    """
    cfg = get_config(backend_id)
    return bool(cfg.get("is_local")) and not cfg.get("is_remote")


def get_default_backend(
    capability: str = PRIMARY_CAPABILITY,
    *,
    require_available: bool = True,
    allow_remote: bool = False,
) -> str:
    """Pick a sensible default backend id for a capability.

    Strategy (ASR-tuned): prefer a backend explicitly flagged ``default_for`` the
    capability *and* whose dependency is importable; then any importable backend
    for the capability; then — if ``require_available`` is False or nothing is
    installed — the first registered candidate (using it will raise a helpful
    install error).

    Only **local** backends (``is_local``) are ever chosen implicitly, so a default
    call never uploads audio to a third party. Pass ``allow_remote=True`` to let
    remote services be chosen too, after every local candidate.
    """
    _discover_backends()

    all_candidates = list_backends(capability)
    candidates = (
        all_candidates if allow_remote else [b for b in all_candidates if is_local(b)]
    )
    if not candidates:
        raise ValueError(
            f"No {'' if allow_remote else 'local '}backends registered for "
            f"capability {capability!r}. Install one (see scribed.requirements)"
            + (
                "."
                if allow_remote
                else ", or name a remote backend explicitly "
                "(backend=...) or pass allow_remote=True."
            )
        )

    flagged = [
        bid
        for bid in candidates
        if capability in _registry[bid]["config"].get("default_for", [])
    ]
    # Local before remote (a no-op unless allow_remote); sorted() is stable.
    by_locality = sorted(candidates, key=lambda b: not is_local(b))

    if require_available:
        for pool in (flagged, by_locality):
            for bid in pool:
                if _is_available(bid):
                    return bid
    if require_available and not allow_remote:
        skipped = [
            b for b in all_candidates if b not in candidates and _is_available(b)
        ]
        if skipped:
            warnings.warn(
                f"No local backend is installed; not using the installed remote "
                f"backend(s) {skipped} implicitly, as that would upload your audio. "
                "Name one (backend=...) or pass allow_remote=True to use it, or "
                "install a local backend (see scribed.requirements).",
                stacklevel=2,
            )
    # Fall back to a declared default, else the first candidate.
    return flagged[0] if flagged else by_locality[0]


def clear_registry() -> None:
    """Clear all registered backends (useful for tests)."""
    global _discovered
    _registry.clear()
    _discovered = False
