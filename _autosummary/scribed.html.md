# scribed

scribed — one facade over many speech-to-text engines, plus a ledger to choose.

Transcription (“turn this audio into text”) is solved a dozen different ways:
local engines (Whisper, faster-whisper, whisper.cpp, Vosk), fast cheap cloud APIs
(Groq, OpenAI), and feature-rich premium services (Deepgram, AssemblyAI, Google,
ElevenLabs) — each with its own install, API, pricing, latency, language coverage,
diarization support, and quirks. scribed gives you:

1. **A uniform facade.** Call [`transcribe()`](#scribed.transcribe) and get the same
   [`Transcript`](scribed.base.html.md#scribed.base.Transcript) back no matter which backend ran:
   ```default
   import scribed
   t = scribed.transcribe("talk.mp3")          # default (first installed) backend
   print(t)                                     # -> the transcript text
   t = scribed.transcribe("talk.mp3", backend="deepgram", diarize=True)
   print(t.srt)                                 # -> SRT subtitles
   for seg in t:
       print(seg.start, seg.speaker, seg.text)
   ```

   Convenience: [`transcribe_text()`](#scribed.transcribe_text) returns just the string.
2. **A ledger / gallery** of *every* engine we researched — not only the ones
   with a working facade — so you can choose with eyes open:
   ```default
   scribed.catalog                                  # the whole ledger
   scribed.find(is_local=True, open_source=True)    # filter it
   scribed.find(diarization="yes", is_remote=True)
   scribed.catalog.to_dataframe()                   # browse as a table
   ```

   The ledger lives in data (`scribed/data/backends.json`), not code.
3. **Tools to build new facades.** The catalog is large; scribed ships a facade
   for a curated subset and gives you the machinery (and a SKILL) to add any
   other one in minutes:
   ```default
   from scribed.make_backend import scaffold_backend, validate_adapter
   scaffold_backend("speechmatics")   # generate a backend package from the ledger
   validate_adapter("faster-whisper") # smoke-test an adapter end to end
   ```

Three tiers of access, from simplest to most powerful:

```default
scribed.transcribe(audio)                              # facade, default backend
scribed.services.deepgram.transcribe(audio, diarize=True)  # pick a backend
scribed.services.deepgram.adapter                      # raw engine adapter
```

### Module Attributes

| [`services`](#scribed.services)   | Singleton service collection for per-backend access (`services.deepgram`).   |
|-------------------------------------------------------------|------------------------------------------------------------------------------|

### Functions

| [`read_transcript`](#scribed.read_transcript)(source, \*[, fmt])                 | Read `source` (a path to a transcript file, or the transcript text itself).                                     |
|-----------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------|
| [`transcribe`](#scribed.transcribe)(audio, \*[, backend])                   | Transcribe audio with any backend, returning a normalized result.                                               |
| [`transcribe_text`](#scribed.transcribe_text)(audio, \*[, backend])              | Like [`transcribe()`](#scribed.transcribe) but returns just the transcript text string. |
| [`find`](#scribed.find)(\*\*criteria)                                 | Filter the ledger; shorthand for `scribed.catalog.Catalog.filter()`.                                            |
| [`list_backends`](#scribed.list_backends)([capability])                        | Sorted ids of implemented backends, optionally filtered by capability.                                          |
| [`register_backend`](#scribed.register_backend)(backend_id, config[, adapter])    | Register a backend at runtime (for third-party plugins).                                                        |
| [`get_default_backend`](#scribed.get_default_backend)([capability, ...])             | Pick a sensible default backend id for a capability.                                                            |
| [`get_config`](#scribed.get_config)(backend_id)                             | A backend's `BACKEND_CONFIG` without loading its adapter.                                                       |
| [`make_segment`](#scribed.make_segment)(text, \*[, start, end, ...])          | Build a normalized [`Segment`](scribed.base.html.md#scribed.base.Segment).               |
| [`make_word`](#scribed.make_word)(text, \*[, start, end, confidence, ...]) | Build a normalized [`Word`](scribed.base.html.md#scribed.base.Word).                     |
| [`scaffold_backend`](#scribed.scaffold_backend)(backend_id, \*[, dest, ...])      | Create a new `scribed/backends/<id>/` package from the template.                                                |
| [`validate_adapter`](#scribed.validate_adapter)(backend_id, \*[, audio, ...])     | Smoke-test a backend adapter end to end, returning a report dict.                                               |
| [`requirements`](#scribed.requirements)(backend_id, \*[, gpu])                | Return structured install [`Requirements`](#scribed.Requirements) for `backend_id`.       |
| [`check`](#scribed.check)(backend_id)                                  | Is `backend_id` importable / usable right now? (no install, no network).                                        |
| [`doctor`](#scribed.doctor)()                                           | Report which implemented backends are usable now and what the rest need.                                        |
| [`install`](#scribed.install)(backend_id, \*[, yes, gpu, verify, ...])   | Plan (and optionally run) the pip install for a backend.                                                        |
| [`available_backends`](#scribed.available_backends)()                               | Implemented backends whose dependency is importable right now.                                                  |
| [`backend_ids`](#scribed.backend_ids)([level, info, test_audio])             | Sorted backend ids at a readiness `level` (one of `LEVELS`).                                                    |
| [`backend_info`](#scribed.backend_info)([ids, run_tests, test_audio])         | Per-backend status: every ledger field plus `implemented`/`set_up`/`tested`.                                    |
| [`status_table`](#scribed.status_table)([ids, info, columns, ...])            | Render an aligned Markdown table of backend status (also plain-text readable).                                  |
| [`names_with_sites`](#scribed.names_with_sites)(ids, \*[, info])                  | `"Name (website), Name2 (website2), ..."` for `ids` (name, not id).                                             |
| [`is_set_up`](#scribed.is_set_up)(backend_id)                              | Ready to run here & now.                                                                                        |
| [`is_tested`](#scribed.is_tested)(backend_id, \*[, audio])                 | Actually run transcription on `audio` (a generated tone if None); True iff it worked.                           |

### Classes

| [`Transcript`](#scribed.Transcript)(text[, segments, backend, ...])        | The normalized result of transcribing audio with any backend.                                                    |
|----------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------|
| [`Segment`](#scribed.Segment)(text[, span, confidence, speaker, ...])   | One recognized span of speech (an utterance / chunk).                                                            |
| [`Word`](#scribed.Word)(text[, span, confidence, speaker])           | A single recognized word, with its own [`TimeSpan`](#scribed.TimeSpan) when available. |
| [`TimeSpan`](#scribed.TimeSpan)(start_ms, end_ms)                        | A half-open `[start_ms, end_ms)` interval in **integer milliseconds**.                                           |
| [`Channel`](#scribed.Channel)(\*values)                                 | Which capture channel a segment came from (optional, `None` for generic STT).                                    |
| [`BackendInfo`](#scribed.BackendInfo)(record, \*[, implemented])            | One backend's ledger entry: a read-only record, by key or by attribute.                                          |
| [`Catalog`](#scribed.Catalog)([path, \_records])                        | scribed's ledger: `ocracy.kit.ledger.Catalog` bound to scribed's data.                                           |
| [`ServiceCollection`](#scribed.ServiceCollection)()                               | Lazy mapping of backend ids -> `ServiceHandle`.                                                                  |
| [`BaseTranscriberAdapter`](#scribed.BaseTranscriberAdapter)(config)                    | Optional base class for backend adapters.                                                                        |
| [`Requirements`](#scribed.Requirements)(backend_id, implemented, ...[, ...]) | What a backend needs to run — structured for an agent to act on.                                                 |

### *class* scribed.BackendInfo(record, , implemented=False)

Bases: [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)

One backend’s ledger entry: a read-only record, by key or by attribute.

New fields added to the JSON are available at once (`info.price_note`,
`info["price_note"]`) with no code change; a few common fields get typed
properties.

### *class* scribed.BaseTranscriberAdapter(config)

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

Native-streaming backends set [`natively_streams`](#scribed.BaseTranscriberAdapter.natively_streams) and override
`_stream_native()`; everyone else streams for free here via the
VAD-segmented batch fallback. `kwargs` flow to the per-utterance
`transcribe` (e.g. `language=`).

### *class* scribed.Catalog(path=None, , \_records=None)

Bases: `Catalog`

scribed’s ledger: `ocracy.kit.ledger.Catalog` bound to scribed’s data.

Loaded lazily from `DEFAULT_LEDGER_PATH` (override via the `path`
argument or the `SCRIBED_LEDGER` environment variable). `filter()`
returns a *new* `Catalog` over the matching subset, so filters compose:

```default
catalog.filter(is_remote=True).filter(pricing_model="free_tier_then_paid")
```

### *class* scribed.Channel(\*values)

Bases: [`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Enum`](https://docs.python.org/3/library/enum.html#enum.Enum)

Which capture channel a segment came from (optional, `None` for generic STT).

Generic single-source transcription leaves [`Segment.channel`](#scribed.Segment.channel) as `None`.
Multi-source consumers (e.g. a meeting recorder capturing the microphone and
the system output separately) stamp the channel so “who spoke” survives all the
way down: `MIC` is the local user, `SYSTEM` is everyone else,
`MIXED` is a single/unknown source.

### *class* scribed.Requirements(backend_id, implemented, available, is_local, is_remote, pip_command, extra=None, system=list(), system_note=None, gpu=None, weights=None, heavy=False, alternative=None, credentials=list(), notes=list())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

What a backend needs to run — structured for an agent to act on.

#### instructions()

An agent-/human-readable, copy-pasteable install plan.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### *class* scribed.Segment(text, span=None, confidence=None, speaker=None, language=None, channel=None, is_final=True, words=(), meta=dict())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

One recognized span of speech (an utterance / chunk).

The main structured unit. A diarized speaker turn is just a segment whose
`speaker` is set. Frozen — enrich by copying (`with_speaker` /
`with_channel` / [`dataclasses.replace()`](https://docs.python.org/3/library/dataclasses.html#dataclasses.replace)), never mutate.

#### text

The recognized text for this span.

* **Type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

#### span

The segment’s time span (ms), if the backend reports timestamps.

* **Type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`TimeSpan`](scribed.base.html.md#scribed.base.TimeSpan)]

#### confidence

Recognition confidence in `[0, 1]` (normalized), if any.

* **Type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`float`](https://docs.python.org/3/builtins/functions.html#float)]

#### speaker

Speaker label (e.g. `"A"`, `"speaker_0"`) when diarized.

* **Type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

#### language

Detected/declared language code for this span, if any.

* **Type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

#### channel

Capture provenance (mic/system/…) for multi-source consumers;
`None` for generic single-source transcription.

* **Type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Channel`](scribed.base.html.md#scribed.base.Channel)]

#### is_final

`True` for a finalized segment (always so for batch); a live
streaming engine sets `False` on interim (partial) hypotheses.

* **Type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

#### words

Word-level units when the backend reports word timestamps.

* **Type:**
  [`Tuple`](https://docs.python.org/3/library/typing.html#typing.Tuple)[[`Word`](scribed.base.html.md#scribed.base.Word), [`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis)]

#### meta

Backend-specific extras (avg_logprob, no_speech_prob, engine, …).

* **Type:**
  [`Mapping`](https://docs.python.org/3/library/typing.html#typing.Mapping)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

#### *property* end *: [Optional](https://docs.python.org/3/library/typing.html#typing.Optional)[[float](https://docs.python.org/3/builtins/functions.html#float)]*

End time in **float seconds** (convenience), or `None` if untimed.

#### offset(by_ms)

Return a copy with `span` shifted later by `by_ms` (absolute time).

* **Return type:**
  [`Segment`](scribed.base.html.md#scribed.base.Segment)

#### *property* start *: [Optional](https://docs.python.org/3/library/typing.html#typing.Optional)[[float](https://docs.python.org/3/builtins/functions.html#float)]*

Start time in **float seconds** (convenience), or `None` if untimed.

#### with_channel(channel)

Return a copy carrying a capture-channel label (frozen -> copy).

* **Return type:**
  [`Segment`](scribed.base.html.md#scribed.base.Segment)

#### with_speaker(speaker)

Return a copy carrying a speaker label (frozen -> copy, don’t mutate).

* **Return type:**
  [`Segment`](scribed.base.html.md#scribed.base.Segment)

### *class* scribed.ServiceCollection

Bases: [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)

Lazy mapping of backend ids -> `ServiceHandle`.

Supports dict-style (`services['deepgram']`) and attribute-style
(`services.deepgram`) access.

### *class* scribed.TimeSpan(start_ms, end_ms)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A half-open `[start_ms, end_ms)` interval in **integer milliseconds**.

Integer time — never bare float seconds — so it is accumulation-safe (offsetting
a live stream’s spans never accrues float drift), hashable, and round-trippable.
The temporal analog of a bounding box.

```pycon
>>> TimeSpan(0, 1500).duration_ms
1500
>>> TimeSpan.from_seconds(1.0, 3.5).as_seconds
(1.0, 3.5)
```

#### *property* as_seconds *: [Tuple](https://docs.python.org/3/library/typing.html#typing.Tuple)[[float](https://docs.python.org/3/builtins/functions.html#float), [float](https://docs.python.org/3/builtins/functions.html#float)]*

`(start, end)` in float seconds (the format/subtitle boundary).

#### *property* duration_ms *: [int](https://docs.python.org/3/builtins/functions.html#int)*

Length of the interval in milliseconds (clamped at 0).

#### *classmethod* from_seconds(start, end)

Build a span from float seconds (e.g. from an STT engine’s output).

* **Return type:**
  [`TimeSpan`](scribed.base.html.md#scribed.base.TimeSpan)

#### offset(by_ms)

Return a copy shifted later by `by_ms` (e.g. to absolute stream time).

* **Return type:**
  [`TimeSpan`](scribed.base.html.md#scribed.base.TimeSpan)

### *class* scribed.Transcript(text, segments=(), backend='', language=None, duration=None, sample_rate=None, raw=None, meta=dict())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

The normalized result of transcribing audio with any backend.

`text` is the headline payload: the full transcript in time order.
`segments` carries the structured spans (with times/speakers/confidences)
when the backend provides them. `raw` is the untouched backend output.
`meta` holds cross-cutting extras (model, timing, …).

Frozen: build via [`from_text()`](#scribed.Transcript.from_text) / [`from_segments()`](#scribed.Transcript.from_segments) or the constructor;
derive variants with [`with_meta()`](#scribed.Transcript.with_meta) / [`filter_confidence()`](#scribed.Transcript.filter_confidence).

Progressive disclosure:

```default
t = scribed.transcribe("talk.mp3")
print(t)                 # -> the transcript text
t.text                   # -> the same string
for seg in t:            # -> iterate Segments
    print(seg.start, seg.speaker, seg.text)   # seg.start in seconds
t.words                  # -> flattened word-level units
t.speakers               # -> sorted speaker labels (if diarized)
t.srt                    # -> SRT subtitles
t.vtt                    # -> WebVTT subtitles
t.raw                    # -> engine-specific structure
```

#### as_srt()

Render timed segments as SubRip (.srt). Segments without times are skipped.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

#### as_vtt()

Render timed segments as WebVTT (.vtt). Segments without times are skipped.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

#### at_speaker(speaker)

Segments attributed to a given speaker.

* **Return type:**
  [`List`](https://docs.python.org/3/library/typing.html#typing.List)[[`Segment`](scribed.base.html.md#scribed.base.Segment)]

#### *property* duration_ms *: [Optional](https://docs.python.org/3/library/typing.html#typing.Optional)[[int](https://docs.python.org/3/builtins/functions.html#int)]*

Total duration in milliseconds (convenience), or `None` if unknown.

#### filter_confidence(min_confidence)

Return a copy keeping only segments at or above `min_confidence`.

Segments without a confidence are dropped. `text` is rebuilt from the
surviving segments.

* **Return type:**
  [`Transcript`](scribed.base.html.md#scribed.base.Transcript)

#### *classmethod* from_segments(segments, , backend='', raw=None, text=None, joiner=' ', language=None, duration=None, sample_rate=None, \*\*meta)

Build a result from structured segments.

If `text` is not given it is synthesized by joining the segments’ text
in their given order with `joiner` (callers should pass segments
already in time order, or pre-join and pass `text` explicitly).

* **Return type:**
  [`Transcript`](scribed.base.html.md#scribed.base.Transcript)

#### *classmethod* from_text(text, , backend='', raw=None, \*\*meta)

Build a minimal result from just a text string (no timing/segments).

* **Return type:**
  [`Transcript`](scribed.base.html.md#scribed.base.Transcript)

#### *property* mean_confidence *: [Optional](https://docs.python.org/3/library/typing.html#typing.Optional)[[float](https://docs.python.org/3/builtins/functions.html#float)]*

Mean confidence over segments that report one, or `None`.

#### *classmethod* parse(source, , fmt=None)

Read an existing transcript (SRT, WebVTT, TextGrid, word JSON, plain).

`source` is a file path or the transcript text itself; `fmt` overrides
format detection. See [`scribed.readers.read_transcript()`](scribed.readers.html.md#scribed.readers.read_transcript).

* **Return type:**
  [`Transcript`](scribed.base.html.md#scribed.base.Transcript)

#### *property* speakers *: [List](https://docs.python.org/3/library/typing.html#typing.List)[[str](https://docs.python.org/3/builtins/stdtypes.html#str)]*

Sorted distinct speaker labels across segments (empty if undiarized).

#### *property* srt *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)*

SRT subtitles built from timed segments (empty string if untimed).

#### *property* vtt *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)*

WebVTT subtitles built from timed segments (empty string if untimed).

#### with_meta(\*\*kw)

Return a copy with extra metadata merged in (frozen -> copy).

* **Return type:**
  [`Transcript`](scribed.base.html.md#scribed.base.Transcript)

#### *property* words *: [List](https://docs.python.org/3/library/typing.html#typing.List)[[Word](scribed.base.html.md#scribed.base.Word)]*

All word-level units, flattened across segments (may be empty).

### *class* scribed.Word(text, span=None, confidence=None, speaker=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A single recognized word, with its own [`TimeSpan`](#scribed.TimeSpan) when available.

#### text

The recognized word.

* **Type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

#### span

The word’s time span (ms), if the backend reports word timestamps.

* **Type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`TimeSpan`](scribed.base.html.md#scribed.base.TimeSpan)]

#### confidence

Recognition confidence in `[0, 1]` (normalized by scribed
from whatever scale the backend used), if available.

* **Type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`float`](https://docs.python.org/3/builtins/functions.html#float)]

#### speaker

Speaker label for this word, if diarized at word level.

* **Type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

#### *property* end *: [Optional](https://docs.python.org/3/library/typing.html#typing.Optional)[[float](https://docs.python.org/3/builtins/functions.html#float)]*

End time in **float seconds** (convenience), or `None` if untimed.

#### *property* start *: [Optional](https://docs.python.org/3/library/typing.html#typing.Optional)[[float](https://docs.python.org/3/builtins/functions.html#float)]*

Start time in **float seconds** (convenience), or `None` if untimed.

### scribed.available_backends()

Implemented backends whose dependency is importable right now.

* **Return type:**
  [`List`](https://docs.python.org/3/library/typing.html#typing.List)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### scribed.backend_ids(level='all', , info=None, test_audio=None)

Sorted backend ids at a readiness `level` (one of `LEVELS`).

Pass a precomputed `info` (from [`backend_info()`](#scribed.backend_info)) to avoid recomputation
— important for `"tested"`, which otherwise re-runs transcription.

* **Return type:**
  [`List`](https://docs.python.org/3/library/typing.html#typing.List)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### scribed.backend_info(ids=None, , run_tests=False, test_audio=None)

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

### scribed.check(backend_id)

Is `backend_id` importable / usable right now? (no install, no network).

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### scribed.doctor()

Report which implemented backends are usable now and what the rest need.

Returns `{"available": [...], "missing": {id: one-line install hint}}`.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### scribed.find(\*\*criteria)

Filter the ledger; shorthand for `scribed.catalog.Catalog.filter()`.

Example:

```default
scribed.find(is_local=True, open_source=True, diarization="yes")
scribed.find(implemented=True)        # only backends scribed can run now
```

* **Return type:**
  [`Catalog`](#scribed.Catalog)

### scribed.get_config(backend_id)

A backend’s `BACKEND_CONFIG` without loading its adapter.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### scribed.get_default_backend(capability='transcribe', , require_available=True)

Pick a sensible default backend id for a capability.

Strategy (ASR-tuned): prefer a backend explicitly flagged `default_for` the
capability *and* whose dependency is importable; then any importable backend
for the capability; then — if `require_available` is False or nothing is
installed — the first registered candidate (using it will raise a helpful
install error).

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### scribed.install(backend_id, , yes=False, gpu=False, verify=True, upgrade=False)

Plan (and optionally run) the pip install for a backend.

With `yes=False` (default) this is a **dry run**: it returns the plan
without changing anything — call `result['requirements'].instructions()` to
show it. With `yes=True` it runs `pip install` for the backend’s extra in
the current interpreter, then (if `verify`) checks importability.

System dependencies and GPU wheels are *surfaced*, never run automatically
(they need sudo/brew or an environment-specific CUDA choice) — run those
yourself from `result['requirements'].system` / `.gpu`.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### scribed.is_set_up(backend_id)

Ready to run here & now.

Requires the engine/client to be importable (local *and* remote), and — for a
remote backend — its (primary) credential env var to resolve. So a remote
whose key is set but whose client library isn’t installed is *not* set up
(it couldn’t actually run). Returns False for ledger-only backends.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### scribed.is_tested(backend_id, , audio=None)

Actually run transcription on `audio` (a generated tone if None); True iff it worked.

For remote backends this performs a real API call. Returns False if the
backend isn’t set up or the run fails.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### scribed.list_backends(capability=None)

Sorted ids of implemented backends, optionally filtered by capability.

A backend matches `capability` if it appears in the backend’s
`capabilities` list (the primary `"transcribe"` is implied for all).

* **Return type:**
  [`List`](https://docs.python.org/3/library/typing.html#typing.List)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### scribed.make_segment(text, , start=None, end=None, confidence=None, conf_scale=1.0, speaker=None, language=None, words=None, \*\*meta)

Build a normalized [`Segment`](scribed.base.html.md#scribed.base.Segment).

`start`/`end` are **seconds** (converted to the millisecond
[`TimeSpan`](scribed.base.html.md#scribed.base.TimeSpan) internally). `confidence` is normalized to
`[0, 1]` via `conf_scale` (e.g. `conf_scale=100` for percent-scale
engines).

* **Return type:**
  [`Segment`](scribed.base.html.md#scribed.base.Segment)

### scribed.make_word(text, , start=None, end=None, confidence=None, conf_scale=1.0, speaker=None)

Build a normalized [`Word`](scribed.base.html.md#scribed.base.Word).

`start`/`end` are **seconds** (converted to the millisecond
[`TimeSpan`](scribed.base.html.md#scribed.base.TimeSpan) internally). `confidence` is normalized to
`[0, 1]` via `conf_scale`.

* **Return type:**
  [`Word`](scribed.base.html.md#scribed.base.Word)

### scribed.names_with_sites(ids, , info=None)

`"Name (website), Name2 (website2), ..."` for `ids` (name, not id).

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### scribed.read_transcript(source, , fmt=None)

Read `source` (a path to a transcript file, or the transcript text itself).

`fmt` (one of `FORMATS`) overrides detection. The result’s `backend`
is `"file:<fmt>"`.

```pycon
>>> t = read_transcript("carl: Hello.\nned: Hi.")
>>> t.speakers, t.backend, t.segments[0].span
(['carl', 'ned'], 'file:plain', None)
```

* **Return type:**
  [`Transcript`](scribed.base.html.md#scribed.base.Transcript)

### scribed.register_backend(backend_id, config, adapter=None)

Register a backend at runtime (for third-party plugins).

* **Parameters:**
  * **backend_id** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Unique identifier.
  * **config** ([`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)) – `BACKEND_CONFIG`-shaped dict (needs at least `name`).
  * **adapter** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Optional pre-instantiated adapter; else loaded lazily from
    `config['module_path']` when first used.
* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### scribed.requirements(backend_id, , gpu=False)

Return structured install [`Requirements`](#scribed.Requirements) for `backend_id`.

Works for both implemented backends (uses the `scribed[extra]` install and
the recipe) and ledger-only backends (falls back to the ledger’s
`python_install` string). Pass `gpu=True` to surface GPU wheel guidance.

* **Return type:**
  [`Requirements`](#scribed.Requirements)

### scribed.scaffold_backend(backend_id, , dest=None, overwrite=False, ledger=None, extra_overrides=None)

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
  * **ledger** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – A [`Catalog`](#scribed.Catalog) to read the record from
    (defaults to the shipped catalog).
  * **extra_overrides** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]) – Extra config-key overrides applied on top of the record.
* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)
* **Returns:**
  The path to the created backend package.

### scribed.services *= <ServiceCollection backends=['assemblyai', 'deepgram', 'elevenlabs', 'faster-whisper', 'google-speech', 'groq', 'openai', 'vosk', 'whisper', 'whispercpp']>*

Singleton service collection for per-backend access (`services.deepgram`).

### scribed.status_table(ids=None, , info=None, columns=None, run_tests=False, test_audio=None)

Render an aligned Markdown table of backend status (also plain-text readable).

Rows are ordered tested → set-up → implemented → listed, then by name, so the
“live” backends float to the top. Pass a precomputed `info` to avoid re-running
tests; otherwise `run_tests` controls which set-up backends get tested.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### scribed.transcribe(audio, , backend=None, \*\*kwargs)

Transcribe audio with any backend, returning a normalized result.

* **Parameters:**
  * **audio** ([`Union`](https://docs.python.org/3/library/typing.html#typing.Union)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), Path, [`bytes`](https://docs.python.org/3/builtins/stdtypes.html#bytes), BinaryIO, NDArray]) – A path, `http(s)` URL, `bytes`, file-like object, or numpy
    waveform.
  * **backend** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Backend id (see [`list_backends()`](#scribed.list_backends)). Defaults to the first
    *installed* implemented backend (see [`get_default_backend()`](#scribed.get_default_backend)).
  * **\*\*kwargs** – Normalized, backend-translated options (e.g. `language`,
    `diarize`, `word_timestamps`). Unknown options for the chosen
    backend are warned about and dropped.
* **Return type:**
  [`Transcript`](scribed.base.html.md#scribed.base.Transcript)
* **Returns:**
  A [`Transcript`](scribed.base.html.md#scribed.base.Transcript) (`str(t)` is the text; `t.srt` /
  `t.vtt` give subtitles; iterate it for segments).

### scribed.transcribe_text(audio, , backend=None, \*\*kwargs)

Like [`transcribe()`](#scribed.transcribe) but returns just the transcript text string.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### scribed.validate_adapter(backend_id, , audio=None, expect_text=None)

Smoke-test a backend adapter end to end, returning a report dict.

Loads the adapter (reporting unavailability instead of raising), runs
`transcribe` on a generated tone (or supplied `audio`), and checks the
contract: a [`Transcript`](scribed.base.html.md#scribed.base.Transcript) came back. Never raises on a
*recognition* mismatch — it returns what happened so callers can decide.

With a tone (no `audio`), `ok` means “ran and returned a Transcript”.
With `expect_text`, `ok` additionally requires the substring to appear.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### Modules

| [`backends`](scribed.backends.html.md#module-scribed.backends)         | Implemented speech-to-text backends.                                                                               |
|-------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| [`base`](scribed.base.html.md#module-scribed.base)                 | Core types and normalized result objects for scribed.                                                              |
| [`catalog`](scribed.catalog.html.md#scribed.catalog)                  | `ocracy.kit.ledger.Catalog` bound to scribed's data.                                                               |
| [`credentials`](scribed.credentials.html.md#module-scribed.credentials)   | Credential resolution for remote transcription backends.                                                           |
| [`make_backend`](scribed.make_backend.html.md#module-scribed.make_backend) | Abstraction tools for *building* transcription facades.                                                            |
| [`readers`](scribed.readers.html.md#module-scribed.readers)           | Read a transcript back into a [`Transcript`](scribed.base.html.md#scribed.base.Transcript). |
| [`registry`](scribed.registry.html.md#module-scribed.registry)         | Backend discovery, registration, and lazy loading.                                                                 |
| [`status`](scribed.status.html.md#module-scribed.status)             | Backend readiness status — four nested levels, info dicts, and a Markdown table.                                   |
| [`tools`](scribed.tools.html.md#module-scribed.tools)               | Command-line tools for scribed (dispatched via `cw` in `__main__`).                                                |
| [`translation`](scribed.translation.html.md#module-scribed.translation)   | Parameter translation between scribed's normalized kwargs and native engines.                                      |
| [`util`](scribed.util.html.md#module-scribed.util)                 | Audio-input normalization and small shared helpers.                                                                |
