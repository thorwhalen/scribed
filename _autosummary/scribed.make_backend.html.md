# scribed.make_backend

Abstraction tools for *building* transcription facades.

Writing a new backend should be mostly declarative. This module supplies the
reusable machinery so an adapter is just “call the engine, return normalized
segments”:

- [`BaseTranscriberAdapter`](#scribed.make_backend.BaseTranscriberAdapter) — subclass it and implement
  `_transcribe()`; kwarg translation (via the
  > backend’s `param_map`) is handled for you.
- [`make_segment()`](#scribed.make_backend.make_segment) / [`make_word()`](#scribed.make_backend.make_word) / [`normalize_confidence()`](#scribed.make_backend.normalize_confidence) — build
  normalized [`Segment`](scribed.base.html.md#scribed.base.Segment) / [`Word`](scribed.base.html.md#scribed.base.Word) from
  whatever shape the engine returned, including confidence-scale normalization.
- [`scaffold_backend()`](#scribed.make_backend.scaffold_backend) — generate a new `scribed/backends/<id>/` package
  from the template, pre-filled from the ledger entry. This is the one-command
  way to start a facade for any backend in the catalog.
- [`make_test_audio()`](#scribed.make_backend.make_test_audio) / [`validate_adapter()`](#scribed.make_backend.validate_adapter) — smoke-test an adapter end
  to end so you know a new facade actually wires up and returns the right type.

These are the “abstraction tools and skills that know the process” — the
companion `SKILL.md` walks an agent (or human) through using them.

### Functions

| [`make_segment`](#scribed.make_backend.make_segment)(text, \*[, start, end, ...])          | Build a normalized [`Segment`](scribed.base.html.md#scribed.base.Segment).   |
|-----------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------|
| [`make_word`](#scribed.make_backend.make_word)(text, \*[, start, end, confidence, ...]) | Build a normalized [`Word`](scribed.base.html.md#scribed.base.Word).         |
| [`normalize_confidence`](#scribed.make_backend.normalize_confidence)(value, \*[, scale])           | Normalize a raw confidence to `[0, 1]` (dividing by `scale`).                                       |
| [`scaffold_backend`](#scribed.make_backend.scaffold_backend)(backend_id, \*[, dest, ...])      | Create a new `scribed/backends/<id>/` package from the template.                                    |
| [`make_test_audio`](#scribed.make_backend.make_test_audio)(\*[, duration, sample_rate, freq]) | Return WAV `bytes` of a short sine tone (needs numpy + soundfile).                                  |
| [`validate_adapter`](#scribed.make_backend.validate_adapter)(backend_id, \*[, audio, ...])     | Smoke-test a backend adapter end to end, returning a report dict.                                   |

### Classes

| [`BaseTranscriberAdapter`](#scribed.make_backend.BaseTranscriberAdapter)(config)   | Optional base class for backend adapters.   |
|-----------------------------------------------------------------------------------|---------------------------------------------|

### *class* scribed.make_backend.BaseTranscriberAdapter(config)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Optional base class for backend adapters.

Stores the config, builds a kwarg translator from `config['param_map']`,
and implements `transcribe` as: translate normalized kwargs -> native
kwargs -> `_transcribe()`. Subclasses implement `_transcribe()` and
return a [`Transcript`](scribed.base.html.md#scribed.base.Transcript).

Adapters are not *required* to subclass this — the registry only needs an
`Adapter` class with a `transcribe(audio, **kwargs)` method — but doing
so removes the boilerplate.

#### natively_streams *: [bool](https://docs.python.org/3/builtins/functions.html#bool)* *= False*

Override to `True` in a backend that talks a live protocol (WebSocket /
streaming recognizer) and implements `_stream_native()`. When `False`
(the default), live transcription is synthesized from batch `transcribe`.

#### *async* transcribe_live(source, , vad=None, \*\*kwargs)

Stream [`Segment`](scribed.base.html.md#scribed.base.Segment)s from a live `AudioSource`.

Native-streaming backends set [`natively_streams`](#scribed.make_backend.BaseTranscriberAdapter.natively_streams) and override
`_stream_native()`; everyone else streams for free here via the
VAD-segmented batch fallback. `kwargs` flow to the per-utterance
`transcribe` (e.g. `language=`).

### scribed.make_backend.make_segment(text, , start=None, end=None, confidence=None, conf_scale=1.0, speaker=None, language=None, words=None, \*\*meta)

Build a normalized [`Segment`](scribed.base.html.md#scribed.base.Segment).

`start`/`end` are **seconds** (converted to the millisecond
[`TimeSpan`](scribed.base.html.md#scribed.base.TimeSpan) internally). `confidence` is normalized to
`[0, 1]` via `conf_scale` (e.g. `conf_scale=100` for percent-scale
engines).

* **Return type:**
  [`Segment`](scribed.base.html.md#scribed.base.Segment)

### scribed.make_backend.make_test_audio(, duration=1.0, sample_rate=16000, freq=440.0)

Return WAV `bytes` of a short sine tone (needs numpy + soundfile).

A tone carries no speech, so it is a *wiring* smoke test: it proves an
adapter accepts audio, runs, and returns a [`Transcript`](scribed.base.html.md#scribed.base.Transcript)
of the right shape. To check actual recognition, pass a real speech clip to
[`validate_adapter()`](#scribed.make_backend.validate_adapter) via `audio=` together with `expect_text=`.

* **Return type:**
  [`bytes`](https://docs.python.org/3/builtins/stdtypes.html#bytes)

### scribed.make_backend.make_word(text, , start=None, end=None, confidence=None, conf_scale=1.0, speaker=None)

Build a normalized [`Word`](scribed.base.html.md#scribed.base.Word).

`start`/`end` are **seconds** (converted to the millisecond
[`TimeSpan`](scribed.base.html.md#scribed.base.TimeSpan) internally). `confidence` is normalized to
`[0, 1]` via `conf_scale`.

* **Return type:**
  [`Word`](scribed.base.html.md#scribed.base.Word)

### scribed.make_backend.normalize_confidence(value, , scale=1.0)

Normalize a raw confidence to `[0, 1]` (dividing by `scale`).

`None` passes through. Use `scale=100` for engines that report `0..100`.
Engines that report a log-probability should convert before calling this.

* **Return type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`float`](https://docs.python.org/3/builtins/functions.html#float)]

### scribed.make_backend.scaffold_backend(backend_id, , dest=None, overwrite=False, ledger=None, extra_overrides=None)

Create a new `scribed/backends/<id>/` package from the template.

Pre-fills `config.py` from the backend’s ledger entry (if any) so you only
have to flesh out `param_map` and implement `adapter.py`’s
`_transcribe`.

* **Parameters:**
  * **backend_id** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The ledger id (e.g. `"deepgram"`, `"faster-whisper"`).
    The on-disk module name uses underscores; the config `id` keeps the
    id verbatim.
  * **dest** ([`Union`](https://docs.python.org/3/library/typing.html#typing.Union)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path), [`None`](https://docs.python.org/3/builtins/constants.html#None)]) – Target directory (defaults to `scribed/backends/<id_underscored>`).
  * **overwrite** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Allow writing into an existing non-empty directory.
  * **ledger** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – A [`Catalog`](scribed.html.md#scribed.Catalog) to read the record from
    (defaults to the shipped catalog).
  * **extra_overrides** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]) – Extra config-key overrides applied on top of the record.
* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)
* **Returns:**
  The path to the created backend package.

### scribed.make_backend.validate_adapter(backend_id, , audio=None, expect_text=None)

Smoke-test a backend adapter end to end, returning a report dict.

Loads the adapter (reporting unavailability instead of raising), runs
`transcribe` on a generated tone (or supplied `audio`), and checks the
contract: a [`Transcript`](scribed.base.html.md#scribed.base.Transcript) came back. Never raises on a
*recognition* mismatch — it returns what happened so callers can decide.

With a tone (no `audio`), `ok` means “ran and returned a Transcript”.
With `expect_text`, `ok` additionally requires the substring to appear.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)
