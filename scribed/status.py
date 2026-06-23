"""Backend readiness status — four nested levels, info dicts, and a Markdown table.

scribed describes far more ASR engines than any one machine has ready to run, so
it helps to know, at a glance, where each one stands. Four **nested** levels:

1. **all** — every engine in the ledger (``scribed/data/backends.json``).
2. **implemented** — scribed ships a working facade for it (``⊆ all``).
3. **set_up** — ready to run *here, now*: the engine/client library is importable
   and, for a remote backend, its credential env var is present (``⊆ implemented``).
4. **tested** — actually produced a transcript from a tone clip on this machine
   (``⊆ set_up``).

``all ⊇ implemented ⊇ set_up ⊇ tested``.

API:

- :func:`backend_ids` — the id list at a level.
- :func:`backend_info` — ``{id: {...all ledger fields..., implemented, set_up, tested}}``.
- :func:`status_table` — an aligned Markdown table (also readable as plain text).
- :func:`names_with_sites` — ``"Name (website), ..."`` for a set of ids.

Note: computing **tested** runs real transcription — for *remote* backends that
means a real (possibly billed) API call. Use the ``run_tests`` argument to
control exactly which backends get called.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    "LEVELS",
    "is_set_up",
    "is_tested",
    "backend_ids",
    "backend_info",
    "status_table",
    "names_with_sites",
]

LEVELS = ("all", "implemented", "set_up", "tested")


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------


def _implemented_ids() -> set:
    from scribed import registry

    return set(registry.list_backends())


def is_set_up(backend_id: str) -> bool:
    """Ready to run here & now.

    Requires the engine/client to be importable (local *and* remote), and — for a
    remote backend — its (primary) credential env var to resolve. So a remote
    whose key is set but whose client library isn't installed is *not* set up
    (it couldn't actually run). Returns False for ledger-only backends.
    """
    from scribed import registry
    from scribed.install import check

    if backend_id not in _implemented_ids():
        return False
    if not check(backend_id):  # engine / client library importable?
        return False
    cfg = registry.get_config(backend_id)
    if cfg.get("is_remote") and not cfg.get("is_local"):
        # Remote also needs its credential present.
        from scribed.credentials import resolve_credential

        try:
            return bool(
                resolve_credential(
                    backend_id, env_var=cfg.get("api_env_var") or None, required=False
                )
            )
        except Exception:
            return False
    return True


def is_tested(backend_id: str, *, audio: Any = None) -> bool:
    """Actually run transcription on ``audio`` (a generated tone if None); True iff it worked.

    For remote backends this performs a real API call. Returns False if the
    backend isn't set up or the run fails.
    """
    if not is_set_up(backend_id):
        return False
    from scribed.make_backend import validate_adapter

    try:
        report = validate_adapter(backend_id, audio=audio)
    except Exception:
        return False
    return bool(report.get("ok"))


# ---------------------------------------------------------------------------
# Info (the single source of computed truth)
# ---------------------------------------------------------------------------


def _test_target_ids(run_tests, set_up_ids: List[str]) -> set:
    """Resolve which set-up backends to actually test, from the ``run_tests`` arg."""
    if run_tests is True:
        return set(set_up_ids)
    if run_tests is False or run_tests is None:
        return set()
    return set(run_tests) & set(set_up_ids)  # an explicit collection of ids


def backend_info(
    ids: Optional[Iterable[str]] = None,
    *,
    run_tests=False,
    test_audio: Any = None,
) -> Dict[str, dict]:
    """Per-backend status: every ledger field plus ``implemented``/``set_up``/``tested``.

    Args:
        ids: Which backends (default: every ledger id).
        run_tests: Which set-up backends to actually transcription-test. ``True`` =
            all set-up (real API calls for remotes!); ``False`` = none (``tested``
            is ``None``); or an iterable of ids to limit testing to those.
        test_audio: Audio to test with (default: a generated tone, shared across all).

    Returns:
        ``{id: {..., "name", "website", "implemented", "set_up", "tested"}}`` where
        ``tested`` is ``True``/``False``/``None`` (None = not attempted).
    """
    from scribed.catalog import catalog

    if ids is None:
        ids = sorted(catalog.ids)
    ids = list(ids)
    implemented = _implemented_ids()

    set_up_ids = [i for i in ids if i in implemented and is_set_up(i)]
    to_test = _test_target_ids(run_tests, set_up_ids)
    if to_test and test_audio is None:
        from scribed.make_backend import make_test_audio

        test_audio = make_test_audio()

    out: Dict[str, dict] = {}
    for i in ids:
        rec = catalog[i].to_dict() if i in catalog else {"id": i}
        info = dict(rec)
        info["implemented"] = i in implemented
        info["set_up"] = i in set_up_ids
        info["website"] = rec.get("homepage", "")
        if i in to_test:
            info["tested"] = is_tested(i, audio=test_audio)
        else:
            info["tested"] = None
        out[i] = info
    return out


def backend_ids(
    level: str = "all",
    *,
    info: Optional[Dict[str, dict]] = None,
    test_audio: Any = None,
) -> List[str]:
    """Sorted backend ids at a readiness ``level`` (one of :data:`LEVELS`).

    Pass a precomputed ``info`` (from :func:`backend_info`) to avoid recomputation
    — important for ``"tested"``, which otherwise re-runs transcription.
    """
    if level not in LEVELS:
        raise ValueError(f"Unknown level {level!r}; expected one of {LEVELS}")

    if info is not None:
        if level == "all":
            return sorted(info)
        key = {"implemented": "implemented", "set_up": "set_up", "tested": "tested"}[
            level
        ]
        return sorted(i for i, d in info.items() if d.get(key) is True)

    from scribed import registry
    from scribed.catalog import catalog

    if level == "all":
        return sorted(catalog.ids)
    implemented = sorted(registry.list_backends())
    if level == "implemented":
        return implemented
    set_up = [i for i in implemented if is_set_up(i)]
    if level == "set_up":
        return set_up
    # tested
    from scribed.make_backend import make_test_audio

    aud = test_audio if test_audio is not None else make_test_audio()
    return [i for i in set_up if is_tested(i, audio=aud)]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _where(d: dict) -> str:
    if d.get("is_local") and d.get("is_remote"):
        return "both"
    if d.get("is_local"):
        return "local"
    if d.get("is_remote"):
        return "remote"
    return "?"


def _flag(value) -> str:
    return {True: "✓", False: "✗", None: ""}.get(value, "")


def _trunc(s: Any, n: int) -> str:
    s = "" if s is None else str(s).replace("|", "/").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


# (header, value-fn) — the default table view. The full per-field data is in backend_info().
_COLUMNS = [
    ("Name", lambda d: _trunc(d.get("name") or d.get("id"), 28)),
    ("Impl", lambda d: _flag(d.get("implemented"))),
    ("Set-up", lambda d: _flag(d.get("set_up"))),
    ("Tested", lambda d: _flag(d.get("tested"))),
    ("Where", _where),
    ("Pricing", lambda d: _trunc(d.get("pricing_model"), 20)),
    ("Accuracy", lambda d: _trunc(d.get("accuracy_tier"), 10)),
    ("Langs", lambda d: str(d.get("languages_count") or "")),
    ("Diar", lambda d: _trunc(d.get("diarization"), 7)),
    ("Stream", lambda d: _trunc(d.get("streaming"), 6)),
    ("Best for", lambda d: _trunc(d.get("best_for"), 44)),
]


def _md_table(headers: List[str], rows: List[List[str]]) -> str:
    cols = list(zip(*([headers] + rows))) if rows else [(h,) for h in headers]
    widths = [max(len(str(c)) for c in col) for col in cols]
    line = lambda cells: (  # noqa: E731
        "| " + " | ".join(str(c).ljust(w) for c, w in zip(cells, widths)) + " |"
    )
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    return "\n".join([line(headers), sep, *[line(r) for r in rows]])


def status_table(
    ids: Optional[Iterable[str]] = None,
    *,
    info: Optional[Dict[str, dict]] = None,
    columns=None,
    run_tests=False,
    test_audio: Any = None,
) -> str:
    """Render an aligned Markdown table of backend status (also plain-text readable).

    Rows are ordered tested → set-up → implemented → listed, then by name, so the
    "live" backends float to the top. Pass a precomputed ``info`` to avoid re-running
    tests; otherwise ``run_tests`` controls which set-up backends get tested.
    """
    if info is None:
        info = backend_info(ids, run_tests=run_tests, test_audio=test_audio)
    elif ids is not None:
        keep = set(ids)
        info = {i: d for i, d in info.items() if i in keep}
    columns = columns or _COLUMNS
    order = sorted(
        info,
        key=lambda i: (
            info[i].get("tested") is not True,
            not info[i].get("set_up"),
            not info[i].get("implemented"),
            info[i].get("name") or i,
        ),
    )
    headers = [h for h, _ in columns]
    rows = [[fn(info[i]) for _, fn in columns] for i in order]
    return _md_table(headers, rows)


def names_with_sites(
    ids: Iterable[str], *, info: Optional[Dict[str, dict]] = None
) -> str:
    """``"Name (website), Name2 (website2), ..."`` for ``ids`` (name, not id)."""
    from scribed.catalog import catalog

    parts = []
    for i in ids:
        d = (info or {}).get(i)
        if d is None:
            d = catalog[i].to_dict() if i in catalog else {"name": i}
        name = d.get("name") or i
        site = d.get("homepage") or d.get("website") or ""
        parts.append(f"{name} ({site})" if site else name)
    return ", ".join(parts)
