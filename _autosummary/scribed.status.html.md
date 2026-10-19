# scribed.status

Backend readiness status — four nested levels, info dicts, and a Markdown table.

scribed describes far more ASR engines than any one machine has ready to run, so
it helps to know, at a glance, where each one stands. Four **nested** levels:

1. **all** — every engine in the ledger (`scribed/data/backends.json`).
2. **implemented** — scribed ships a working facade for it (`⊆ all`).
3. **set_up** — ready to run *here, now*: the engine/client library is importable
   and, for a remote backend, its credential env var is present (`⊆ implemented`).
4. **tested** — actually produced a transcript from a tone clip on this machine
   (`⊆ set_up`).

`all ⊇ implemented ⊇ set_up ⊇ tested`.

API:

- [`backend_ids()`](#scribed.status.backend_ids) — the id list at a level.
- [`backend_info()`](#scribed.status.backend_info) — `{id: {...all ledger fields..., implemented, set_up, tested}}`.
- [`status_table()`](#scribed.status.status_table) — an aligned Markdown table (also readable as plain text).
- [`names_with_sites()`](#scribed.status.names_with_sites) — `"Name (website), ..."` for a set of ids.

#### NOTE
computing **tested** runs real transcription — for *remote* backends that
means a real (possibly billed) API call. Use the `run_tests` argument to
control exactly which backends get called.

### Functions

| [`is_set_up`](#scribed.status.is_set_up)(backend_id)                      | Ready to run here & now.                                                              |
|---------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| [`is_tested`](#scribed.status.is_tested)(backend_id, \*[, audio])         | Actually run transcription on `audio` (a generated tone if None); True iff it worked. |
| [`backend_ids`](#scribed.status.backend_ids)([level, info, test_audio])     | Sorted backend ids at a readiness `level` (one of `LEVELS`).                          |
| [`backend_info`](#scribed.status.backend_info)([ids, run_tests, test_audio]) | Per-backend status: every ledger field plus `implemented`/`set_up`/`tested`.          |
| [`status_table`](#scribed.status.status_table)([ids, info, columns, ...])    | Render an aligned Markdown table of backend status (also plain-text readable).        |
| [`names_with_sites`](#scribed.status.names_with_sites)(ids, \*[, info])          | `"Name (website), Name2 (website2), ..."` for `ids` (name, not id).                   |

### scribed.status.backend_ids(level='all', , info=None, test_audio=None)

Sorted backend ids at a readiness `level` (one of `LEVELS`).

Pass a precomputed `info` (from [`backend_info()`](#scribed.status.backend_info)) to avoid recomputation
— important for `"tested"`, which otherwise re-runs transcription.

* **Return type:**
  [`List`](https://docs.python.org/3/library/typing.html#typing.List)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### scribed.status.backend_info(ids=None, , run_tests=False, test_audio=None)

Per-backend status: every ledger field plus `implemented`/`set_up`/`tested`.

* **Parameters:**
  * **ids** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Iterable`](https://docs.python.org/3/library/typing.html#typing.Iterable)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]) – Which backends (default: every ledger id).
  * **run_tests** – Which set-up backends to actually transcription-test. `True` =
    all set-up (real API calls for remotes!); `False` = none (`tested`
    is `None`); or an iterable of ids to limit testing to those.
  * **test_audio** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Audio to test with (default: a generated tone, shared across all).
* **Return type:**
  [`Dict`](https://docs.python.org/3/library/typing.html#typing.Dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]
* **Returns:**
  `{id: {..., "name", "website", "implemented", "set_up", "tested"}}` where
  `tested` is `True`/`False`/`None` (None = not attempted).

### scribed.status.is_set_up(backend_id)

Ready to run here & now.

Requires the engine/client to be importable (local *and* remote), and — for a
remote backend — its (primary) credential env var to resolve. So a remote
whose key is set but whose client library isn’t installed is *not* set up
(it couldn’t actually run). Returns False for ledger-only backends.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### scribed.status.is_tested(backend_id, , audio=None)

Actually run transcription on `audio` (a generated tone if None); True iff it worked.

For remote backends this performs a real API call. Returns False if the
backend isn’t set up or the run fails.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### scribed.status.names_with_sites(ids, , info=None)

`"Name (website), Name2 (website2), ..."` for `ids` (name, not id).

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### scribed.status.status_table(ids=None, , info=None, columns=None, run_tests=False, test_audio=None)

Render an aligned Markdown table of backend status (also plain-text readable).

Rows are ordered tested → set-up → implemented → listed, then by name, so the
“live” backends float to the top. Pass a precomputed `info` to avoid re-running
tests; otherwise `run_tests` controls which set-up backends get tested.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
