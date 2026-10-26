# scribed.base

Core types and normalized result objects for scribed.

Speech-to-text (ASR) engines disagree wildly on what they return: local Whisper
emits a list of timestamped segments; cloud APIs return nested JSON of
utterances/words with speaker labels and confidences; some engines return only a
plain string. scribed normalizes all of that into a small, stable set of
dataclasses so that callers get the *same shape* regardless of which backend
produced the transcript:

- [`Transcript`](#scribed.base.Transcript) — the full result of transcribing audio: a concatenated
  `text` (in time order) plus a list of structured `segments` carrying time
  spans, speakers and confidences, plus the untouched `raw` backend output for
  power users who need engine-specific detail.
- [`Segment`](#scribed.base.Segment) — one recognized span of speech (an utterance / chunk) with an
  optional [`TimeSpan`](#scribed.base.TimeSpan), `speaker` (when diarized), `confidence` and
  nested word-level [`Word`](#scribed.base.Word) units. Optionally an `is_final` flag (live
  streaming) and a capture `channel` (multi-source capture, e.g. mic vs system).
- [`Word`](#scribed.base.Word) — a single word with its own time span (when the engine reports
  word-level timestamps).
- [`TimeSpan`](#scribed.base.TimeSpan) — a `[start_ms, end_ms)` half-open interval in \*\*integer
  milliseconds\*\*; the temporal analog of a bounding box.

**Time is integer milliseconds, by design.** A transcript is \*standoff interval
annotation\* over the audio: segments reference the audio by time and never carry
the samples. Integer-millisecond time is accumulation-safe (offsetting a live
stream’s spans never drifts), hashable, and round-trippable to a wire format. For
ergonomics, [`Word`](#scribed.base.Word)/[`Segment`](#scribed.base.Segment) also expose read-only `start`/`end`
**float-second** convenience accessors derived from `span` — but `span` (in ms)
is the single source of truth.

The result dataclasses are **frozen** (immutable): a concern enriches a segment by
*copying* (`with_speaker` / `with_channel` / [`dataclasses.replace()`](https://docs.python.org/3/library/dataclasses.html#dataclasses.replace)), never
by mutating in place.

The input side is normalized too: every facade function accepts an
`AudioInput` — a path, URL, `bytes`, file-like object, or numpy waveform.
Concrete decoding happens lazily in [`scribed.util`](scribed.util.html.md#module-scribed.util), so importing scribed
never requires soundfile or numpy.

The design goal is *progressive disclosure*: `str(transcript)` gives you the
text, `transcript.text` is the same string, iterating yields its segments,
`transcript.srt` / `transcript.vtt` give you subtitles, and
`transcript.segments` / `transcript.raw` are there when you need structure.

### Classes

| [`Channel`](#scribed.base.Channel)(\*values)                               | Which capture channel a segment came from (optional, `None` for generic STT).                                    |
|--------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------|
| [`Segment`](#scribed.base.Segment)(text[, span, confidence, speaker, ...]) | One recognized span of speech (an utterance / chunk).                                                            |
| [`TimeSpan`](#scribed.base.TimeSpan)(start_ms, end_ms)                      | A half-open `[start_ms, end_ms)` interval in **integer milliseconds**.                                           |
| [`Transcript`](#scribed.base.Transcript)(text[, segments, backend, ...])      | The normalized result of transcribing audio with any backend.                                                    |
| [`Word`](#scribed.base.Word)(text[, span, confidence, speaker])         | A single recognized word, with its own [`TimeSpan`](#scribed.base.TimeSpan) when available. |

### *class* scribed.base.Channel(\*values)

Bases: [`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Enum`](https://docs.python.org/3/library/enum.html#enum.Enum)

Which capture channel a segment came from (optional, `None` for generic STT).

Generic single-source transcription leaves [`Segment.channel`](#scribed.base.Segment.channel) as `None`.
Multi-source consumers (e.g. a meeting recorder capturing the microphone and
the system output separately) stamp the channel so “who spoke” survives all the
way down: `MIC` is the local user, `SYSTEM` is everyone else,
`MIXED` is a single/unknown source.

### *class* scribed.base.Segment(text, span=None, confidence=None, speaker=None, language=None, channel=None, is_final=True, words=(), meta=dict())

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
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`TimeSpan`](#scribed.base.TimeSpan)]

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
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Channel`](#scribed.base.Channel)]

#### is_final

`True` for a finalized segment (always so for batch); a live
streaming engine sets `False` on interim (partial) hypotheses.

* **Type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

#### words

Word-level units when the backend reports word timestamps.

* **Type:**
  [`Tuple`](https://docs.python.org/3/library/typing.html#typing.Tuple)[[`Word`](#scribed.base.Word), [`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis)]

#### meta

Backend-specific extras (avg_logprob, no_speech_prob, engine, …).

* **Type:**
  [`Mapping`](https://docs.python.org/3/library/typing.html#typing.Mapping)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

#### *property* end *: [Optional](https://docs.python.org/3/library/typing.html#typing.Optional)[[float](https://docs.python.org/3/builtins/functions.html#float)]*

End time in **float seconds** (convenience), or `None` if untimed.

#### offset(by_ms)

Return a copy with `span` shifted later by `by_ms` (absolute time).

* **Return type:**
  [`Segment`](#scribed.base.Segment)

#### *property* start *: [Optional](https://docs.python.org/3/library/typing.html#typing.Optional)[[float](https://docs.python.org/3/builtins/functions.html#float)]*

Start time in **float seconds** (convenience), or `None` if untimed.

#### with_channel(channel)

Return a copy carrying a capture-channel label (frozen -> copy).

* **Return type:**
  [`Segment`](#scribed.base.Segment)

#### with_speaker(speaker)

Return a copy carrying a speaker label (frozen -> copy, don’t mutate).

* **Return type:**
  [`Segment`](#scribed.base.Segment)

### *class* scribed.base.TimeSpan(start_ms, end_ms)

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
  [`TimeSpan`](#scribed.base.TimeSpan)

#### offset(by_ms)

Return a copy shifted later by `by_ms` (e.g. to absolute stream time).

* **Return type:**
  [`TimeSpan`](#scribed.base.TimeSpan)

### *class* scribed.base.Transcript(text, segments=(), backend='', language=None, duration=None, sample_rate=None, raw=None, meta=dict())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

The normalized result of transcribing audio with any backend.

`text` is the headline payload: the full transcript in time order.
`segments` carries the structured spans (with times/speakers/confidences)
when the backend provides them. `raw` is the untouched backend output.
`meta` holds cross-cutting extras (model, timing, …).

Frozen: build via [`from_text()`](#scribed.base.Transcript.from_text) / [`from_segments()`](#scribed.base.Transcript.from_segments) or the constructor;
derive variants with [`with_meta()`](#scribed.base.Transcript.with_meta) / [`filter_confidence()`](#scribed.base.Transcript.filter_confidence).

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
  [`List`](https://docs.python.org/3/library/typing.html#typing.List)[[`Segment`](#scribed.base.Segment)]

#### *property* duration_ms *: [Optional](https://docs.python.org/3/library/typing.html#typing.Optional)[[int](https://docs.python.org/3/builtins/functions.html#int)]*

Total duration in milliseconds (convenience), or `None` if unknown.

#### filter_confidence(min_confidence)

Return a copy keeping only segments at or above `min_confidence`.

Segments without a confidence are dropped. `text` is rebuilt from the
surviving segments.

* **Return type:**
  [`Transcript`](#scribed.base.Transcript)

#### *classmethod* from_segments(segments, , backend='', raw=None, text=None, joiner=' ', language=None, duration=None, sample_rate=None, \*\*meta)

Build a result from structured segments.

If `text` is not given it is synthesized by joining the segments’ text
in their given order with `joiner` (callers should pass segments
already in time order, or pre-join and pass `text` explicitly).

* **Return type:**
  [`Transcript`](#scribed.base.Transcript)

#### *classmethod* from_text(text, , backend='', raw=None, \*\*meta)

Build a minimal result from just a text string (no timing/segments).

* **Return type:**
  [`Transcript`](#scribed.base.Transcript)

#### *property* mean_confidence *: [Optional](https://docs.python.org/3/library/typing.html#typing.Optional)[[float](https://docs.python.org/3/builtins/functions.html#float)]*

Mean confidence over segments that report one, or `None`.

#### *classmethod* parse(source, , fmt=None)

Read an existing transcript (SRT, WebVTT, TextGrid, word JSON, plain).

`source` is a file path or the transcript text itself; `fmt` overrides
format detection. See [`scribed.readers.read_transcript()`](scribed.readers.html.md#scribed.readers.read_transcript).

* **Return type:**
  [`Transcript`](#scribed.base.Transcript)

#### *property* speakers *: [List](https://docs.python.org/3/library/typing.html#typing.List)[[str](https://docs.python.org/3/builtins/stdtypes.html#str)]*

Sorted distinct speaker labels across segments (empty if undiarized).

#### *property* srt *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)*

SRT subtitles built from timed segments (empty string if untimed).

#### *property* vtt *: [str](https://docs.python.org/3/builtins/stdtypes.html#str)*

WebVTT subtitles built from timed segments (empty string if untimed).

#### with_meta(\*\*kw)

Return a copy with extra metadata merged in (frozen -> copy).

* **Return type:**
  [`Transcript`](#scribed.base.Transcript)

#### *property* words *: [List](https://docs.python.org/3/library/typing.html#typing.List)[[Word](#scribed.base.Word)]*

All word-level units, flattened across segments (may be empty).

### *class* scribed.base.Word(text, span=None, confidence=None, speaker=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A single recognized word, with its own [`TimeSpan`](#scribed.base.TimeSpan) when available.

#### text

The recognized word.

* **Type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

#### span

The word’s time span (ms), if the backend reports word timestamps.

* **Type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`TimeSpan`](#scribed.base.TimeSpan)]

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
