# scribed.registry

Backend discovery, registration, and lazy loading.

An *implemented* backend is a subpackage of [`scribed.backends`](scribed.backends.html.md#module-scribed.backends) that ships
two things:

- `config.py` defining a `BACKEND_CONFIG` dict (id, pip_install, capabilities,
  `param_map`, …), and
- `adapter.py` defining an `Adapter` class whose `transcribe(audio, **kwargs)`
  returns a [`scribed.base.Transcript`](scribed.base.html.md#scribed.base.Transcript).

This registry scans for those at first use, loads each adapter *lazily* (so
importing scribed never imports heavy engine SDKs), and raises a friendly
`pip install` error if a backend’s dependency is missing. Third parties can
register their own backends at runtime via [`register_backend()`](#scribed.registry.register_backend).

The design mirrors the sibling `ocracy` facade, adapted for ASR: the primary
capability is `"transcribe"` (audio -> text+timing), with optional extra
capabilities (`"diarize"`, `"stream"`, `"translate"`, …) declared per
backend. `"whisper_sized_model"` marks backends whose
`model` accepts a bare Whisper size (`small`, `large-v3`), so consumers can
derive that set with `list_backends("whisper_sized_model")` rather than hardcode it.

### Module Attributes

| [`PRIMARY_CAPABILITY`](#scribed.registry.PRIMARY_CAPABILITY)   | The capability every general ASR backend provides.   |
|-----------------------------------------------------------------------|------------------------------------------------------|

### Functions

| [`clear_registry`](#scribed.registry.clear_registry)()                                | Clear all registered backends (useful for tests).                         |
|--------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------|
| [`get_backend`](#scribed.registry.get_backend)(backend_id)                         | Config + lazily-loaded adapter for a backend (raises on missing deps).    |
| [`get_config`](#scribed.registry.get_config)(backend_id)                          | A backend's `BACKEND_CONFIG` without loading its adapter.                 |
| [`get_default_backend`](#scribed.registry.get_default_backend)([capability, ...])          | Pick a sensible default backend id for a capability.                      |
| [`is_local`](#scribed.registry.is_local)(backend_id)                            | Does `backend_id` run entirely on this machine (never uploads audio)?     |
| [`list_backends`](#scribed.registry.list_backends)([capability])                     | Sorted ids of implemented backends, optionally filtered by capability.    |
| [`register_backend`](#scribed.registry.register_backend)(backend_id, config[, adapter]) | Register a backend at runtime (for third-party plugins).                  |
| [`sdk_problem`](#scribed.registry.sdk_problem)(backend_id)                         | Why the installed SDK does not suit `backend_id`, or `None` when it does. |

### scribed.registry.PRIMARY_CAPABILITY *= 'transcribe'*

The capability every general ASR backend provides.

### scribed.registry.clear_registry()

Clear all registered backends (useful for tests).

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### scribed.registry.get_backend(backend_id)

Config + lazily-loaded adapter for a backend (raises on missing deps).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### scribed.registry.get_config(backend_id)

A backend’s `BACKEND_CONFIG` without loading its adapter.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### scribed.registry.get_default_backend(capability='transcribe', , require_available=True, allow_remote=False)

Pick a sensible default backend id for a capability.

Strategy (ASR-tuned): prefer a backend explicitly flagged `default_for` the
capability *and* whose dependency is importable; then any importable backend
for the capability; then — if `require_available` is False or nothing is
installed — the first registered candidate (using it will raise a helpful
install error).

Only **local** backends (`is_local`) are ever chosen implicitly, so a default
call never uploads audio to a third party. Pass `allow_remote=True` to let
remote services be chosen too, after every local candidate.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### scribed.registry.is_local(backend_id)

Does `backend_id` run entirely on this machine (never uploads audio)?

A config lacking `is_local` (e.g. a third-party plugin that does not say) or
flagged `is_remote` counts as *not* local: the safe reading.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### scribed.registry.list_backends(capability=None)

Sorted ids of implemented backends, optionally filtered by capability.

A backend matches `capability` if it appears in the backend’s
`capabilities` list (the primary `"transcribe"` is implied for all).

* **Return type:**
  [`List`](https://docs.python.org/3/library/typing.html#typing.List)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### scribed.registry.register_backend(backend_id, config, adapter=None)

Register a backend at runtime (for third-party plugins).

* **Parameters:**
  * **backend_id** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Unique identifier.
  * **config** ([`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)) – `BACKEND_CONFIG`-shaped dict (needs at least `name`). Set
    `is_local: True` for a backend that never uploads audio: without it
    the backend is never chosen as an implicit default.
  * **adapter** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Optional pre-instantiated adapter; else loaded lazily from
    `config['module_path']` when first used.
* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### scribed.registry.sdk_problem(backend_id)

Why the installed SDK does not suit `backend_id`, or `None` when it does.

A backend whose config states `sdk_requirement` (a requirement string such as
`groq>=0.20.0`) needs an installed distribution in that range: an older SDK
lacks parameters the adapter sends, and would otherwise be reported as ready
and fail on a missing keyword. (A test keeps these equal to the extras in
`pyproject.toml`.) A distribution that cannot be read counts as fine. Cached:
reading metadata is slow.

* **Return type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]
