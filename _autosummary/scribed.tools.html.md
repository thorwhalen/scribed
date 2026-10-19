# scribed.tools

Command-line tools for scribed (dispatched via `cw` in `__main__`).

Each function here is a thin, CLI-friendly wrapper over the Python API; `cw`
turns their signatures into subcommands and options. Run `scribed <command>
--help` (after `pip install 'scribed[cli]'`) or `python -m scribed <command>`.

### Functions

| [`transcribe`](#scribed.tools.transcribe)(audio, \*[, backend, language, ...])   | Transcribe an audio file/URL and print the result.                                  |
|----------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|
| [`backends`](#scribed.tools.backends)(\*[, capability])                        | List the backends scribed can run right now (optionally by capability).             |
| [`info`](#scribed.tools.info)(backend_id)                                  | Print a backend's full ledger record as JSON.                                       |
| [`find`](#scribed.tools.find)(\*[, local, remote, free, implemented, ...]) | Filter the ledger and print matching backends (id, where, pricing, best-for).       |
| [`scaffold`](#scribed.tools.scaffold)(backend_id, \*[, dest])                  | Generate a new backend package from its ledger entry.                               |
| [`validate`](#scribed.tools.validate)(backend_id)                              | Smoke-test a backend adapter end to end and print the report.                       |
| [`requirements`](#scribed.tools.requirements)(backend_id, \*[, gpu])               | Show what a backend needs to run (pip, system deps, GPU, weights, creds).           |
| [`doctor`](#scribed.tools.doctor)()                                          | Report which backends are usable now, and how to install the rest.                  |
| [`install`](#scribed.tools.install)(backend_id, \*[, gpu, yes])               | Plan (default) or run (`--yes`) the pip install for a backend.                      |
| [`status`](#scribed.tools.status)(\*[, level, run_tests, names])             | Print an ASR-backend readiness table (levels: all ⊇ implemented ⊇ set_up ⊇ tested). |

### scribed.tools.backends(, capability=None)

List the backends scribed can run right now (optionally by capability).

* **Parameters:**
  **capability** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – Filter to a capability, e.g. `diarize`, `stream`, `translate`.

### scribed.tools.doctor()

Report which backends are usable now, and how to install the rest.

### scribed.tools.find(, local=False, remote=False, free=False, implemented=False, diarization=False, streaming=False, word_timestamps=False, language=None)

Filter the ledger and print matching backends (id, where, pricing, best-for).

Flags compose (AND). Example: `scribed find --local --free --diarization`.

* **Parameters:**
  * **local** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Keep only backends that run locally.
  * **remote** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Keep only hosted/remote backends.
  * **free** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Keep only free / open-source backends.
  * **implemented** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Keep only backends scribed can run today.
  * **diarization** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Keep only backends that label speakers.
  * **streaming** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Keep only backends that support real-time streaming.
  * **word_timestamps** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Keep only backends that emit word-level timestamps.
  * **language** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – Keep only backends whose languages mention this name/code.

### scribed.tools.info(backend_id)

Print a backend’s full ledger record as JSON.

* **Parameters:**
  **backend_id** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – A ledger id, e.g. `deepgram` (see `scribed find`).

### scribed.tools.install(backend_id, , gpu=False, yes=False)

Plan (default) or run (`--yes`) the pip install for a backend.

Without `--yes` it prints the plan and changes nothing. System deps and GPU
wheels are surfaced, not run automatically.

* **Parameters:**
  * **backend_id** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Backend id to install, e.g. `faster-whisper`.
  * **gpu** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Surface GPU-wheel guidance.
  * **yes** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Actually run `pip install` (otherwise just print the plan).

### scribed.tools.requirements(backend_id, , gpu=False)

Show what a backend needs to run (pip, system deps, GPU, weights, creds).

* **Parameters:**
  * **backend_id** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Backend id, e.g. `whisper`.
  * **gpu** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Include GPU-wheel guidance.

### scribed.tools.scaffold(backend_id, , dest=None)

Generate a new backend package from its ledger entry.

* **Parameters:**
  * **backend_id** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The ledger id to scaffold (e.g. `speechmatics`).
  * **dest** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – Optional destination directory.

### scribed.tools.status(, level='all', run_tests=False, names=False)

Print an ASR-backend readiness table (levels: all ⊇ implemented ⊇ set_up ⊇ tested).

* **Parameters:**
  * **level** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Restrict rows to a level: `all` | `implemented` | `set_up` | `tested`.
  * **run_tests** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Actually transcription-test the set-up backends — makes real API
    calls for set-up remotes (off by default, so a plain `scribed status` never bills you).
  * **names** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Also print, per level, a comma-separated `Name (website)` list.

### scribed.tools.transcribe(audio, , backend=None, language=None, diarize=False, output='text')

Transcribe an audio file/URL and print the result.

* **Parameters:**
  * **audio** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Path or http(s) URL to the audio.
  * **backend** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – Backend id (default: first installed). See `scribed backends`.
  * **language** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – Language code hint, e.g. `en` (omit to auto-detect).
  * **diarize** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Ask the backend to label speakers (if it supports it).
  * **output** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – `text` (default), `json` (text + segments), `srt`, or `vtt`.

### scribed.tools.validate(backend_id)

Smoke-test a backend adapter end to end and print the report.

* **Parameters:**
  **backend_id** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The backend id to validate (e.g. `faster-whisper`).
