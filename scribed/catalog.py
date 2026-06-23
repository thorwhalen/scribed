"""The ledger: a data-driven gallery of speech-to-text backends.

scribed ships a *ledger* — a JSON catalog (``scribed/data/backends.json``) that
describes **every** ASR engine/service we know about, whether or not scribed
ships a working facade for it. Keeping this data *out of the code* is deliberate:
the catalog is curated research, it changes far more often than the code, and
users (and downstream tools) can read, filter, diff, and extend it without
touching Python.

This module reads that JSON and exposes it as a filterable, dict-like
:class:`Catalog` of :class:`BackendInfo` records::

    from scribed import catalog

    catalog["faster-whisper"]                       # one backend's info
    catalog.filter(is_local=True, open_source=True)  # only local OSS engines
    catalog.filter(diarization="yes")               # engines that label speakers
    catalog.filter(implemented=True)                # only what scribed can run today
    catalog.supports_language("French")             # engines that list French
    catalog.to_dataframe()                          # pandas view (if installed)

Each record follows the schema documented in ``data/SCHEMA.md``. The special
``implemented`` flag is computed *live* from the backend registry, so it can
never drift from the code: a backend is "implemented" iff a real adapter exists
under :mod:`scribed.backends`.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Union

__all__ = ["BackendInfo", "Catalog", "catalog", "DEFAULT_LEDGER_PATH"]

DEFAULT_LEDGER_PATH = Path(__file__).parent / "data" / "backends.json"

# Fields whose meaning is "membership in a free-text description", handled
# specially by :meth:`Catalog.filter` rather than by exact equality.
_TEXT_MEMBERSHIP_FIELDS = {
    "languages_note",
    "beyond_text",
    "output_formats",
    "pros",
    "cons",
}


class BackendInfo(Mapping):
    """One backend's ledger entry — a read-only, attribute-and-dict accessible record.

    Wraps the raw record dict so that new fields added to the JSON are available
    immediately (via attribute or key access) without code changes, while a few
    commonly used fields get typed properties for convenience and discoverability.
    """

    def __init__(self, record: dict, *, implemented: bool = False):
        # Store a shallow copy plus the live-computed implemented flag.
        self._record: Dict[str, Any] = dict(record)
        self._record.setdefault("implemented", implemented)

    # -- Mapping interface (dict-like) -------------------------------------
    def __getitem__(self, key: str) -> Any:
        return self._record[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._record)

    def __len__(self) -> int:
        return len(self._record)

    # -- attribute access ---------------------------------------------------
    def __getattr__(self, name: str) -> Any:
        # Only called when normal attribute lookup fails.
        try:
            return self._record[name]
        except KeyError:
            raise AttributeError(name)

    # -- common typed conveniences -----------------------------------------
    @property
    def id(self) -> str:
        return self._record.get("id", "")

    @property
    def name(self) -> str:
        return self._record.get("name", self.id)

    @property
    def is_local(self) -> bool:
        return bool(self._record.get("is_local", False))

    @property
    def is_remote(self) -> bool:
        return bool(self._record.get("is_remote", False))

    @property
    def implemented(self) -> bool:
        return bool(self._record.get("implemented", False))

    def to_dict(self) -> dict:
        return dict(self._record)

    def __repr__(self) -> str:
        where = (
            "+".join(
                w
                for w, on in (("local", self.is_local), ("remote", self.is_remote))
                if on
            )
            or "?"
        )
        impl = "implemented" if self.implemented else "listed"
        return f"<BackendInfo {self.id!r} [{where}] {impl}>"


def _matches(info: BackendInfo, field: str, wanted: Any) -> bool:
    """Whether a single ``field == wanted`` criterion holds for ``info``.

    Equality by default; for free-text fields (``languages_note``,
    ``beyond_text``, ``output_formats``, ``pros``, ``cons``) a case-insensitive
    *membership* test is used. A ``wanted`` that is a set/list/tuple means "value
    is one of these".
    """
    value = info._record.get(field)

    if field in _TEXT_MEMBERSHIP_FIELDS:
        hay = value if isinstance(value, str) else " ".join(map(str, value or []))
        needles = wanted if isinstance(wanted, (set, list, tuple)) else [wanted]
        return any(str(n).lower() in hay.lower() for n in needles)

    if isinstance(wanted, (set, list, tuple)):
        return value in wanted
    return value == wanted


class Catalog(Mapping):
    """A filterable, dict-like collection of :class:`BackendInfo`, keyed by id.

    Loaded lazily from :data:`DEFAULT_LEDGER_PATH` (override via the ``path``
    argument or the ``SCRIBED_LEDGER`` environment variable). :meth:`filter`
    returns a *new* ``Catalog`` over the matching subset, so filters compose::

        catalog.filter(is_remote=True).filter(pricing_model="free_tier_then_paid")
    """

    def __init__(
        self,
        path: Optional[Union[str, Path]] = None,
        *,
        _records: Optional[List[dict]] = None,
    ):
        self._path = Path(path) if path else None
        self._explicit_records = _records
        self._cache: Optional[Dict[str, BackendInfo]] = None

    # -- loading ------------------------------------------------------------
    def _resolve_path(self) -> Path:
        if self._path is not None:
            return self._path
        env = os.environ.get("SCRIBED_LEDGER")
        return Path(env) if env else DEFAULT_LEDGER_PATH

    def _load(self) -> Dict[str, BackendInfo]:
        if self._cache is not None:
            return self._cache

        if self._explicit_records is not None:
            records = self._explicit_records
        else:
            path = self._resolve_path()
            if not path.exists():
                records = []
            else:
                data = json.loads(path.read_text(encoding="utf-8"))
                records = data["backends"] if isinstance(data, dict) else data

        implemented_ids = self._implemented_ids()
        self._cache = {
            r["id"]: BackendInfo(r, implemented=r["id"] in implemented_ids)
            for r in records
        }
        return self._cache

    @staticmethod
    def _implemented_ids() -> set:
        """Ids of backends with a real adapter, computed live from the registry."""
        try:
            from scribed import registry

            return set(registry.list_backends())
        except Exception:
            return set()

    # -- Mapping interface --------------------------------------------------
    def __getitem__(self, key: str) -> BackendInfo:
        try:
            return self._load()[key]
        except KeyError:
            raise KeyError(
                f"Unknown backend id: {key!r}. "
                f"Known ids: {sorted(self._load().keys())[:20]}..."
            )

    def __iter__(self) -> Iterator[str]:
        return iter(self._load())

    def __len__(self) -> int:
        return len(self._load())

    # -- filtering / querying ----------------------------------------------
    def filter(
        self,
        *,
        predicate: Optional[Callable[[BackendInfo], bool]] = None,
        implemented: Optional[bool] = None,
        **criteria: Any,
    ) -> "Catalog":
        """Return a new ``Catalog`` of backends matching every criterion.

        Args:
            predicate: An arbitrary ``BackendInfo -> bool`` callable.
            implemented: If set, keep only (un)implemented backends.
            **criteria: ``field=value`` constraints. ``value`` may be a
                set/list/tuple meaning "one of". Free-text fields
                (``languages_note``, ``beyond_text``, ``output_formats``,
                ``pros``, ``cons``) use a case-insensitive substring match.

        Example::

            catalog.filter(is_local=True, open_source=True, diarization="yes")
        """
        items = self._load().values()

        def keep(info: BackendInfo) -> bool:
            if implemented is not None and info.implemented is not implemented:
                return False
            if predicate is not None and not predicate(info):
                return False
            return all(_matches(info, f, v) for f, v in criteria.items())

        return Catalog(_records=[i.to_dict() for i in items if keep(i)])

    def supports_language(self, language: str) -> "Catalog":
        """Backends whose ``languages_note`` mentions ``language`` (name or code)."""
        return self.filter(languages_note=language)

    def can(self, capability: str) -> "Catalog":
        """Backends advertising a ``capability`` beyond plain transcription.

        Matches either the ``beyond_text`` list or a ``<capability>`` field set
        to ``"yes"`` (e.g. ``diarization``, ``streaming``, ``word_timestamps``,
        ``translation``).
        """
        return self.filter(
            predicate=lambda i: (
                capability in (i._record.get("beyond_text") or [])
                or i._record.get(capability) in ("yes", True)
            )
        )

    # -- export -------------------------------------------------------------
    @property
    def ids(self) -> List[str]:
        return sorted(self._load().keys())

    def to_records(self) -> List[dict]:
        return [i.to_dict() for i in self._load().values()]

    def to_dataframe(self, *, columns: Optional[Iterable[str]] = None):
        """Return a pandas DataFrame of the catalog (pandas imported lazily)."""
        from scribed.util import check_import

        pd = check_import("pandas", install_hint="pandas", feature="to_dataframe()")
        df = pd.DataFrame(self.to_records())
        if columns is not None:
            df = df[list(columns)]
        return df

    def compare(
        self,
        ids: Optional[Iterable[str]] = None,
        *,
        fields: Iterable[str] = (
            "name",
            "is_local",
            "is_remote",
            "open_source",
            "pricing_model",
            "price_note",
            "accuracy_tier",
            "languages_count",
            "streaming",
            "diarization",
            "word_timestamps",
            "best_for",
        ),
    ) -> List[dict]:
        """A trimmed, side-by-side view of selected backends and fields."""
        chosen = list(ids) if ids is not None else self.ids
        fields = list(fields)
        out = []
        for i in chosen:
            info = self[i]
            row = {"id": info.id}
            row.update({f: info._record.get(f) for f in fields})
            out.append(row)
        return out

    def __repr__(self) -> str:
        records = self._load()
        n = len(records)
        n_impl = sum(1 for i in records.values() if i.implemented)
        n_local = sum(1 for i in records.values() if i.is_local)
        n_remote = sum(1 for i in records.values() if i.is_remote)
        return (
            f"<Catalog {n} backends | {n_impl} implemented | "
            f"{n_local} local, {n_remote} remote>"
        )


# Module-level singleton — the canonical ledger.
catalog = Catalog()
