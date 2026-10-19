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

The loader itself is :mod:`ocracy.kit.ledger`, shared with the other fleet facades
(ocracy's own ledger uses it); this module binds scribed's data to it: the ledger
path, the ``SCRIBED_LEDGER`` override, the registry, and the ASR-specific fields.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

from ocracy.kit.ledger import DEFAULT_TEXT_FIELDS, BackendInfo
from ocracy.kit.ledger import Catalog as _LedgerCatalog

__all__ = ["BackendInfo", "Catalog", "catalog", "DEFAULT_LEDGER_PATH"]

DEFAULT_LEDGER_PATH = Path(__file__).parent / "data" / "backends.json"
LEDGER_ENV_VAR = "SCRIBED_LEDGER"

# Fields whose meaning is "membership in a free-text description", handled
# specially by :meth:`Catalog.filter` rather than by exact equality.
_TEXT_MEMBERSHIP_FIELDS = DEFAULT_TEXT_FIELDS | {"pros", "cons"}

_COMPARE_FIELDS = (
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
)


def _implemented_ids() -> set:
    """Ids of backends with a real adapter, computed live from the registry."""
    try:
        from scribed import registry

        return set(registry.list_backends())
    except Exception:
        return set()


class Catalog(_LedgerCatalog):
    """scribed's ledger: :class:`ocracy.kit.ledger.Catalog` bound to scribed's data.

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
        super().__init__(
            path,
            records=_records,
            default_path=DEFAULT_LEDGER_PATH,
            env_var=LEDGER_ENV_VAR,
            implemented=_implemented_ids,
            text_fields=_TEXT_MEMBERSHIP_FIELDS,
            compare_fields=_COMPARE_FIELDS,
        )


# Module-level singleton — the canonical ledger.
catalog = Catalog()
