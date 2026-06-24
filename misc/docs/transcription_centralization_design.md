# Recommended Architecture: Centralizing Transcription in scribed

> **Provenance.** Design produced by a multi-agent workflow (8 deep readers over
> both packages → 3 independent architecture stances → 3 adversarial judge lenses
> → synthesis), then **independently verified against the source** by the author.
> See *Verification status* below for what was checked and the refinements found.
> Status: **proposal for maintainer review** — not yet implemented. Several genuine
> decisions (§8) are the maintainer's call before any code changes.

---

## Verification status (checked against the code, not just asserted)

**Confirmed true (load-bearing):**

- `scribed.make_backend.make_segment` / `make_word` exist and take **float-second**
  `start=`/`end=` kwargs; every adapter builds results *only* through them +
  `Transcript.from_segments(...)` (verified in `backends/whisper/adapter.py`). ⇒ the
  int-ms `TimeSpan` reshape is absorbable *inside* those two helpers, leaving all
  ~10 adapter call-sites untouched. This is the linchpin of the "bounded breakage"
  risk claim, and it holds.
- `_logprob_to_conf` is genuinely duplicated (scribed whisper adapter ↔ hearing
  `stt.py`). Confirmed dup-deletion, not a port. (Note: scribed uses `math.exp`,
  hearing uses `np.clip(np.exp(...))`; pick faster_whisper's normalization as
  canonical when collapsing.)
- hearing's "real-time" path is **VAD-segmented batch**, not native streaming, and
  emits **finals only** (`meta['final']=True`) — no interim partials exist today.
  ⇒ "move real-time into scribed" really means "design the streaming interface
  *properly* (native + VAD-fallback + partials), then port hearing's pipeline."
- The two data models genuinely diverge on principle: scribed `TimeSpan` = **float
  seconds** (mutable `Segment`, SRT/VTT export); hearing `TimeSpan` = **int ms**
  (frozen/slots, standoff-annotation theory, accumulation-safe). Not an accident.
- hearing `live_transcribe` is a solid async design worth preserving (per-channel
  `asyncio.Queue` fan-out, supervisor, backpressure, fire-and-forget agents).

**Refinements found (fold into §7 step 1 — they enlarge the enumerated edit
slightly but keep it bounded):**

- `make_backend.validate_adapter` (the `has_timing` check) also reads `s.start` →
  must become `s.span is not None` / `s.span.start_ms`.
- The current `Segment` carries a `level: str` field + a module-level `LEVELS`
  tuple that the reshaped frozen `Segment` drops. Grep `level` / `LEVELS` usage
  before removing; `make_segment(..., level=...)` loses that parameter.
- `make_segment` currently passes `words` as a `list`; the frozen/slots `Segment`
  wants `words: tuple[Word, ...]` — internal change to `make_segment` only.

**Not yet verified (synthesis flagged these for migration step 5–6; confirm before
relying on them):** exact `hearing/http_app.py` `segment_to_dict` field set and the
`meta['final']` read; `hearing/storage.py` `transcript_from_json` round-trip
(does it preserve `is_final`/`words`/`meta`?); whether a root-level `hearing`
integration test exercises `transcribe`/`live_transcribe` today.

---

## Decisions locked (maintainer, this session)

These four were decided and are no longer open; the rest of §8 remains open.

1. **Type model → adopt hearing's int-ms frozen spine.** scribed's public
   `Segment`/`Transcript` is reshaped to frozen/slots, `span: TimeSpan` in integer
   milliseconds, with `is_final`/`channel` as typed fields. The one-time break is
   accepted (its own signed-off, test-rewritten PR — §7 step 1). Resolves §8-Q3.
2. **Capture scope → scribed gets generic sources.** `from_mic()` (single generic
   device) + `file_to_stream()` (hardware-free CI harness) live in scribed; macOS
   `DeviceCapture` (BlackHole/Aggregate) + channel-split stay in hearing. Resolves
   §8-Q2.
3. **Streaming surface → async canonical + a thin sync driver.** `transcribe_live`
   is the async generator; **additionally** ship `iter_live(...)`, a synchronous
   driver that pumps the async stream on a private event loop and yields to a plain
   `for`. "Streaming implies async" is *not* the floor — non-async callers get a
   one-liner too. Resolves §8-Q1 (with the sync escape hatch chosen). See §3.4.
4. **`Channel` as a first-class `Optional` field** on scribed's `Segment` — confirmed
   by accepting decision 1's spine (the field is part of it). Resolves §8-Q4.
5. **Naming.** Headline async verb is **`transcribe_live`** (maintainer choice over
   `transcribe_stream`); its sync pair is **`iter_live`**. The `Transcriber` public
   Protocol and the internal `Adapter` class both keep their names (distinct roles);
   the synthesized fallback stays `vad_segmented_stream`. Resolves §8-Q7.

**Recommended, adopting unless you object:** §8-Q5 — a **shared** `scribed.streaming`
push→pull bridge helper (with a thread-safe `feed`), not per-adapter. §8-Q6 — guard
`_discover_backends` with a `threading.Lock` and set `_discovered` *after* the scan
(fixing a latent early-set bug), plus the documented "discover before concurrent
sessions" invariant.

---

## Implementation log

**Step 1 — unified int-ms frozen spine — DONE** (branch `refactor/unified-result-spine`,
not yet committed). `base.py` reshaped: `TimeSpan(start_ms, end_ms)` integer-ms
frozen/slots (`from_seconds`/`as_seconds`/`offset`); `Word`/`Segment` frozen with
`span: TimeSpan` as the stored SSOT; `Segment` gains `channel: Optional[Channel]` +
`is_final: bool` + `with_channel`/`offset`, drops `level`; `Transcript` frozen with
tuple segments + a `duration_ms` accessor (the `duration` *seconds* field stays —
4 adapters pass `duration=`). `Channel` enum added + exported; `LEVELS` removed.
`make_segment`/`make_word` keep their float-second `start=`/`end=` surface and convert
to ms internally (so all 10 adapters are untouched); `make_segment` drops `level=`.

**Refinement vs. the literal plan (lower blast radius):** `Word`/`Segment` expose
**read-only float-second `.start`/`.end` convenience accessors** derived from `span`.
Because of this, `tools.py` JSON output, `make_backend.validate_adapter`'s
`has_timing` check, the SRT/VTT formatter, and the `elevenlabs`/`google_speech`
word-aggregation reads **needed no change** — the only production edits were
`base.py`, `make_backend.py`, and the `LEVELS`→`Channel` export swap. `span` (ms)
remains the single source of truth and the frontend-facing value (no float→int
rounding); seconds accessors are Python ergonomics only.

**Verified:** 32/32 unit tests (incl. new frozen/`is_final`/`channel`/`offset`
tests), full `--doctest-modules` sweep, all 34 modules import, ruff clean, and an
adapter-pattern smoke (elevenlabs/google_speech/tools/SRT) all green.

---

## 1. Executive summary

**The core decision.** scribed becomes the single home for *all* speech-to-text —
batch and real-time — by growing exactly two new things on top of its existing
facade/registry/strategy machinery: (1) **one unified, frozen, integer-millisecond
result spine** (`Transcript`/`Segment`/`Word`/`TimeSpan`) owned by scribed, and
(2) **a second, optional engine verb** `transcribe_live` alongside the existing
`transcribe`, with a framework-synthesized VAD-segmented fallback so every
batch-only backend streams for free. hearing keeps only meeting-app concerns: the
channel trick, diarization choice, agents/RAG, session storage, the FastAPI
transport, and the React frontend. hearing's duplicated STT engines
(`FasterWhisperSTT`, `OpenAISTT`), its VAD module, and its generic
audio-conditioning helpers are deleted and consumed from scribed.

**The boundary.** scribed owns one *logical* stream end-to-end: audio chunks in →
VAD-segmented or natively-streamed → `Segment`s out (interim and final). hearing
owns the *multi-stream orchestration*: the per-channel `asyncio.Queue` fan-out,
the supervisor, push-source backpressure (drop-on-full), the `Channel` "me vs them"
semantics, diarization, and agent fire-and-forget. We state plainly: **scribed does
not solve push-source backpressure** — it provides a clean pull-based single-stream
primitive, and the consumer (hearing) layers queue discipline around it.

**The headline interface.** Batch stays exactly as it is:
`scribed.transcribe(audio, *, backend=None, **kwargs) -> Transcript`, fully
synchronous. Real-time is its symmetric async twin:
`scribed.transcribe_live(source, *, backend=None, vad=None, **kwargs) ->
AsyncIterator[Segment]`, where each `Segment` carries a typed `is_final: bool` field
(replacing hearing's fragile `meta['final']` dict key). A backend opts into native
streaming by implementing one optional method; otherwise the framework synthesizes
streaming from its batch `transcribe` via VAD utterance segmentation. The registry's
existing capability filtering (`list_backends(capability="stream")`,
`get_default_backend(capability="stream")`) routes native-vs-synthesized
transparently with no call-site change — this is the open-closed crown jewel.

**Synthesis posture (where the judges disagreed).** The architecture-purist judge
ranked the protocol-first abstraction shape highest; the type-model lens preferred
full-centralization's unified frozen/int-ms spine with `Channel` as a first-class
optional field; the migration judge insisted the *path* there must be incremental
and test-green at every step, never a big-bang base-type reshape as step 1. **We
adopt all three:** protocol-first's *two-verbs/one-engine composable-stream* design,
full-centralization's *unified frozen int-ms spine with `Optional[Channel]` as a
real field* (rejecting protocol-first's `meta['channel']` exile), and minimal-seam's
*incremental, additive-first, engine-flip-last* migration ordering — with the
breaking base-type reshape explicitly budgeted as its own approved, test-rewritten
sub-project rather than smuggled into the engine move. We also fix the one place the
*current* hearing code is genuinely broken: the streaming fallback must offload the
blocking decode with `asyncio.to_thread` and bound in-flight decodes, which hearing
does not do today.

---

## 2. Core abstractions (with real signatures)

All new code lives in `scribed/base.py` (reshaped spine), `scribed/streaming.py`
(new — protocols + composition), `scribed/vad.py` (moved from hearing), and
`scribed/audio.py` (moved generic conditioning). Convention: **arguments beyond the
first are keyword-only**; `sample_rate` is always keyword-only; no magic numbers
(tuning lives in module constants or small frozen config dataclasses).

### 2.1 Unified result spine — `scribed/base.py` (frozen, slots, integer ms, standoff)

```python
# scribed/base.py
from __future__ import annotations
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Iterable, Iterator, Mapping, Optional, Union
from pathlib import Path

AudioInput = Union[str, Path, bytes, "BinaryIO", "NDArray"]   # batch input (unchanged)
AudioChunk = "NDArray"                                        # one mono float32 block (streaming)


@dataclass(frozen=True, slots=True)
class TimeSpan:
    """Half-open [start_ms, end_ms) in INTEGER milliseconds: accumulation-safe, hashable."""
    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    @classmethod
    def from_seconds(cls, start: float, end: float) -> "TimeSpan":
        return cls(int(round(start * 1000)), int(round(end * 1000)))

    @property
    def as_seconds(self) -> tuple[float, float]:        # read-path bridge for SRT/VTT
        return self.start_ms / 1000.0, self.end_ms / 1000.0

    def offset(self, by_ms: int) -> "TimeSpan":
        return TimeSpan(self.start_ms + by_ms, self.end_ms + by_ms)


class Channel(str, Enum):
    """OPTIONAL capture provenance. Generic STT leaves Segment.channel=None; hearing stamps it."""
    MIC = "mic"
    SYSTEM = "system"
    MIXED = "mixed"


@dataclass(frozen=True, slots=True)
class Word:
    text: str
    span: Optional[TimeSpan] = None
    confidence: Optional[float] = None        # normalized [0, 1]
    speaker: Optional[str] = None


@dataclass(frozen=True, slots=True)
class Segment:
    """The spine unit. Frozen; enrich-by-copy via replace / with_*."""
    text: str
    span: Optional[TimeSpan] = None
    confidence: Optional[float] = None
    speaker: Optional[str] = None             # diarization rides here; scribed leaves None
    language: Optional[str] = None
    channel: Optional[Channel] = None         # FIRST-CLASS optional field (None for generic STT)
    is_final: bool = True                     # FORMALIZED (was hearing meta['final']); batch=True
    words: tuple[Word, ...] = ()
    meta: Mapping[str, Any] = field(default_factory=dict)   # avg_logprob, no_speech_prob, engine...

    def with_speaker(self, speaker: str) -> "Segment":
        return replace(self, speaker=speaker)

    def with_channel(self, channel: Channel) -> "Segment":
        return replace(self, channel=channel)

    def offset(self, by_ms: int) -> "Segment":
        return self if self.span is None else replace(self, span=self.span.offset(by_ms))


@dataclass(frozen=True, slots=True)
class Transcript:
    segments: tuple[Segment, ...] = ()
    backend: str = ""
    language: Optional[str] = None
    duration_ms: Optional[int] = None
    sample_rate: Optional[int] = None
    raw: Any = None                           # untouched native response (lossless escape hatch)
    meta: Mapping[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.segments)

    def __str__(self) -> str: return self.text
    def __iter__(self) -> Iterator[Segment]: return iter(self.segments)
    def __len__(self) -> int: return len(self.segments)
    def __bool__(self) -> bool: return bool(self.segments)

    @property
    def words(self) -> tuple[Word, ...]:
        return tuple(w for s in self.segments for w in s.words)

    @property
    def speakers(self) -> tuple[str, ...]:
        return tuple(sorted({s.speaker for s in self.segments if s.speaker}))

    @property
    def srt(self) -> str: ...                  # uses span.as_seconds at the format boundary
    @property
    def vtt(self) -> str: ...
    def at_speaker(self, speaker: str) -> "Transcript": ...

    @classmethod
    def from_segments(cls, segments: Iterable[Segment], *, backend: str = "", raw: Any = None,
                      language: Optional[str] = None, duration_ms: Optional[int] = None,
                      **meta) -> "Transcript": ...
    @classmethod
    def from_text(cls, text: str, *, backend: str = "", raw: Any = None, **meta) -> "Transcript": ...
```

**Why this shape (resolving the type conflict):** the type-model judge is decisive —
hearing's int-ms/frozen/standoff model is "the more principled SSOT," and adopting
it preserves `merge_segments`, `with_speaker`, `replace`, and the int-ms wire
convention (`startMs`/`endMs`, `clock()`) the frontend already consumes, with **no
float→int rounding at the hottest serialization point**. `Channel` becomes a
first-class `Optional` field (full-centralization), **not** exiled to `meta`
(protocol-first) — the latter re-creates exactly the magic-dict-key fragility that
promoting `is_final` to a field is meant to fix, and it forfeits the zero-projection
HTTP win.

**The adapter-author surface stays float-seconds.** `make_segment(text, *,
start=None, end=None, ...)` and `make_word(...)` keep float-second `start=`/`end=`
kwargs and convert internally via `TimeSpan.from_seconds`. The existing backend
adapters call `make_segment`, so they are **untouched** by the int-ms switch. The
breakage is confined to direct `Segment(...)`/`Word(...)` construction (tests),
`tools.py` JSON output (`s.start` → `s.span.start_ms`), the SRT/VTT formatter
(`span.as_seconds`), `validate_adapter`'s `has_timing` check, and the dropped
`level`/`LEVELS` — a bounded, enumerable, one-time edit the migration owns
explicitly (§7, step 1).

### 2.2 Batch + streaming engine contract — `scribed/streaming.py`

```python
# scribed/streaming.py
from typing import AsyncIterator, Optional, Protocol, runtime_checkable
from scribed.base import AudioInput, AudioChunk, Segment, Transcript


@runtime_checkable
class Transcriber(Protocol):
    """A speech-to-text engine. Batch is REQUIRED; streaming is OPTIONAL."""

    def transcribe(self, audio: AudioInput, **kwargs) -> Transcript:
        """Whole input -> complete Transcript (the existing contract, unchanged shape)."""
        ...

    # OPTIONAL. If absent, the framework synthesizes it from `transcribe` (see §3).
    def transcribe_live(
        self, source: "AudioSource", *, vad: Optional["VAD"] = None, **kwargs
    ) -> AsyncIterator[Segment]:
        """Live audio -> async stream of Segments. Interim segments have is_final=False;
        finalized ones is_final=True. Spans are ABSOLUTE from stream start."""
        ...
```

`BaseTranscriberAdapter` (in `make_backend.py`) gains a default `transcribe_live`
that delegates to the synthesized fallback, plus a capability flag:

```python
# scribed/make_backend.py  — ADDITIONS to BaseTranscriberAdapter
class BaseTranscriberAdapter:
    natively_streams: bool = False            # registry reads this for capability='stream'

    # ... existing __init__, transcribe, _transcribe unchanged ...

    async def transcribe_live(self, source, *, vad=None, **kwargs) -> AsyncIterator[Segment]:
        """DEFAULT: VAD-segmented batch (synthesized streaming). Native-streaming backends
        (deepgram-live, vosk) OVERRIDE _stream_native and set natively_streams=True."""
        if self.natively_streams:
            async for seg in self._stream_native(source, vad=vad, **kwargs):
                yield seg
        else:
            from scribed.streaming import vad_segmented_stream
            async for seg in vad_segmented_stream(self, source, vad=vad, **kwargs):
                yield seg

    async def _stream_native(self, source, *, vad=None, **kwargs) -> AsyncIterator[Segment]:
        raise NotImplementedError("declare natively_streams=True and implement _stream_native")
```

### 2.3 Audio source — a channel-agnostic async-iterable of chunks — `scribed/streaming.py`

```python
@runtime_checkable
class AudioSource(Protocol):
    """A real-time audio source: an async-iterable of mono float32 chunks at a known rate.

    Channel-agnostic ON PURPOSE — multi-channel/Channel routing is the consumer's job
    (hearing demuxes per channel and feeds N AudioSources to N transcribe_live calls)."""
    sample_rate: int
    def __aiter__(self) -> AsyncIterator[AudioChunk]: ...


def file_to_stream(
    audio: AudioInput, *, sample_rate: int = 16_000, block_ms: int = 200, realtime: bool = False
) -> AudioSource:
    """File -> simulated live stream. The hardware-free CI harness for the whole streaming path
    (absorbs hearing.StreamingFileCapture, channel-stripped). realtime=True paces with asyncio.sleep."""


def from_mic(
    *, device: Optional[int | str] = None, block_ms: int = 200, sample_rate: int = 16_000
) -> AudioSource:
    """Generic single-device mic source (NOT the meeting Aggregate Device). Lazy sounddevice."""
```

`DeviceCapture` (macOS BlackHole / Aggregate Device, 4-channel) **stays in hearing**
— it is platform- and meeting-specific.

### 2.4 VAD — moved verbatim from hearing — `scribed/vad.py`

```python
# scribed/vad.py  (moved from hearing/vad.py + rms_energy from hearing/capture.py)
from dataclasses import dataclass
from typing import AsyncIterator, Optional, Protocol, runtime_checkable
from scribed.base import AudioChunk

DEFAULT_SILENCE_MS = 700
DEFAULT_MIN_SPEECH_MS = 200
DEFAULT_MAX_UTTERANCE_MS = 30_000


@runtime_checkable
class VAD(Protocol):
    def is_speech(self, block: AudioChunk, sample_rate: int) -> bool: ...


@dataclass(frozen=True)
class EnergyVAD:                              # dependency-free default
    threshold: float = 0.01
    def is_speech(self, block, sample_rate) -> bool: ...


@dataclass
class SileroVAD:                             # optional neural, lazy torch/silero-vad import
    speech_prob_threshold: float = 0.5
    def is_speech(self, block, sample_rate) -> bool: ...


async def segment_utterances(
    frames: AsyncIterator[AudioChunk], *, sample_rate: int, vad: Optional[VAD] = None,
    silence_ms: int = DEFAULT_SILENCE_MS, min_speech_ms: int = DEFAULT_MIN_SPEECH_MS,
    max_utterance_ms: int = DEFAULT_MAX_UTTERANCE_MS,
) -> AsyncIterator[tuple[AudioChunk, int]]:
    """Stream transform: chunks in -> (utterance_samples, start_ms) out. Verbatim from hearing,
    confirmed channel-agnostic (AsyncIterator[ndarray], no Channel)."""
```

`rms_energy` moves into `scribed/audio.py` (VAD depends on it). The conditioning
helpers `to_mono`, `resample`, `to_mono_16k`, `load_audio`, `STT_SAMPLE_RATE`, and
the ffmpeg fallback also move into `scribed/audio.py`.

### 2.5 The synthesized streaming fallback + the facade — `scribed/streaming.py`

This is the generic real-time engine, expressed as composable async generators — no
orchestrator class. It is hearing's verified `vad_stream_transcribe`, generalized
and **hardened** (the decode is offloaded and bounded; hearing's current code does
neither).

```python
# scribed/streaming.py
import asyncio
from scribed.vad import VAD, segment_utterances
from scribed.audio import to_mono_16k, STT_SAMPLE_RATE


async def vad_segmented_stream(
    engine: Transcriber, source: AudioSource, *, vad: Optional[VAD] = None,
    target_rate: int = STT_SAMPLE_RATE, max_inflight: int = 1, **kwargs,
) -> AsyncIterator[Segment]:
    """Make a NON-streaming engine stream: VAD-segment audio into utterances, batch-transcribe
    each OFF the event loop, offset spans to absolute time, emit is_final=True.

    Hardening over hearing's original:
      * resample to target_rate so a 48k mic feeds a 16k model (§3 fix);
      * blocking decode runs via asyncio.to_thread (event loop never stalls);
      * a bounded semaphore caps in-flight decodes to prevent unbounded head-of-line growth.
    """
    sem = asyncio.Semaphore(max_inflight)

    async def _decode(utterance, start_ms):
        async with sem:
            result = await asyncio.to_thread(
                engine.transcribe, utterance, sample_rate=target_rate, **kwargs
            )
        return [seg.offset(start_ms) for seg in result]   # is_final already True for batch

    frames = _resampled_frames(source, target_rate=target_rate)
    async for utterance, start_ms in segment_utterances(frames, sample_rate=target_rate, vad=vad):
        for seg in await _decode(utterance, start_ms):
            yield seg


def transcribe_live(
    source: AudioSource, *, backend: Optional[str] = None, vad: Optional[VAD] = None, **kwargs
) -> AsyncIterator[Segment]:
    """Tier-1 streaming facade. Resolve backend (prefer capability='stream'); route to the
    adapter's transcribe_live, which is native or VAD-synthesized transparently."""
    import scribed
    name = backend or scribed.get_default_backend(capability="stream")
    adapter = scribed.services[name].adapter
    return adapter.transcribe_live(source, vad=vad, **kwargs)
```

For **native-streaming** backends (Deepgram live WS), `_stream_native` must own an
internal bounded queue that bridges the *server-push* WebSocket into the
*consumer-pull* async-generator contract, reconciling interim/final by message id —
the streaming-domain judge correctly flags this server-push-vs-pull impedance
mismatch as the real engineering work (§3, §8).

---

## 3. Concurrency / streaming model

**The definitive decision: async generators (`async def` + `async for`) are the
canonical streaming surface; batch stays synchronous; no threads as the public
model.** Blocking work (local model decode) is offloaded with `asyncio.to_thread`.
Justification, grounded in all three maps and the streaming-domain judge:

- hearing's *entire* live path is already asyncio (`live_transcribe`,
  `segment_utterances`, `astream`, the NDJSON `StreamingResponse`,
  `AgentConsumer.on_segment`). An async generator composes with the one real
  consumer with zero glue.
- Native cloud streamers (Deepgram WS, OpenAI Realtime SSE) are inherently async
  socket I/O; threads-only would fight them and sync generators cannot `await` a
  socket.
- **Batch is left untouched.** `transcribe(audio) -> Transcript` and every
  `_transcribe` stay plain sync. Adding async is purely additive.

**Partial vs final.** Carried as the typed field `Segment.is_final: bool`, default
`True` (so every batch segment is trivially final), replacing hearing's untyped
`meta['final']`. The frontend's `isFinal` maps directly from `seg.is_final`. To
prevent the silent-mislabel foot-gun the streaming judge named (a native adapter
that forgets to emit interims turns every partial into a "final"), the
native-streaming contract is validated by `validate_stream` (§7).

**One interface, two adaptation paths.**

| Engine class | Mechanism | Latency / UX |
|---|---|---|
| **Native streaming** (deepgram-live WS, vosk `PartialResult`) | `_stream_native(source)` opens the live connection / feeds the recognizer; yields true interim partials then a final per utterance. `natively_streams=True`, `capabilities=['stream']`. Owns an internal bounded queue to bridge server-push → consumer-pull. | ~300 ms partials (Deepgram); incremental (Vosk). Real word-by-word UX. |
| **Batch-only** (faster-whisper, whisper, openai, elevenlabs) | `vad_segmented_stream`: VAD groups chunks into utterances → `await asyncio.to_thread(engine.transcribe, …)` per utterance → `seg.offset(start_ms)`, `is_final=True`. | Latency ≈ `silence_ms` (700 ms) + decode; **finals-only, no interim partials**. Honest "near-real-time," surfaced via `list_backends(capability='stream')`. |

The consumer calls one `transcribe_live(source, backend=…)`; the registry routes
native-vs-synthesized invisibly. We **surface the asymmetry** (not hide it):
`list_backends(capability="stream")` and the ledger `streaming` flag let a consumer
see which engines emit true interim partials, so a local-Whisper default does not
silently masquerade as word-by-word streaming.

**Backpressure — stated as a known boundary.** scribed's `transcribe_live` is a
**pull-based** async generator: a slow consumer naturally throttles the upstream VAD
via `async for`. scribed deliberately does **not** embed a drop-on-full queue
(rejecting full-centralization's design, which the streaming judge showed *stacks
two backpressure regimes* and silently drops audio). **Push-source pacing under a
slow consumer is hearing's responsibility:** hearing's `live_transcribe` keeps the
per-channel `asyncio.Queue(maxsize=…)` fan-out with drop policy.

**Head-of-line blocking under sustained speech** (the gap all three proposals
missed): even with `to_thread`, decoding is serialized per stream — if VAD finalizes
utterance N+1 while decode N runs, latency grows. `vad_segmented_stream` therefore
takes `max_inflight` (default 1 = strict ordering) bounded by a semaphore; raising it
permits a small decode pool at the cost of out-of-order emission. A real knob,
defaulted conservatively, documented as the meeting-monologue failure mode.

**Cancellation.** The async-generator contract gives clean cancellation: closing the
`async for` (or cancelling the driving task) raises `GeneratorExit`/`CancelledError`
into `transcribe_live`, which propagates to `segment_utterances` and any in-flight
`to_thread` future. Native adapters close their WebSocket in a `finally`.

### 3.4 The thin sync driver (maintainer decision: ship it)

Async is canonical, but non-async callers get a one-liner too via a thin synchronous
driver that pumps the async generator on a private event loop. It is deliberately
minimal — no thread, no queue — just step-wise `__anext__` advancement, so it stays a
~12-line shim with no parallel logic to keep in sync with the async path.

```python
# scribed/streaming.py
import asyncio
from typing import Iterator, Optional

def iter_live(
    source: "AudioSource", *, backend: Optional[str] = None,
    vad: Optional["VAD"] = None, **kwargs,
) -> Iterator[Segment]:
    """Synchronous driver over transcribe_live for non-async callers.

        for seg in scribed.iter_live(scribed.from_mic()):
            print("FINAL" if seg.is_final else "...", seg.text)

    Runs the async stream on a PRIVATE event loop and yields each Segment to a plain
    `for`. MUST NOT be called from inside a running event loop (use the async
    `transcribe_live` there) — it raises a clear error if it detects one.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass  # good: no running loop, we own one
    else:
        raise RuntimeError(
            "iter_live() cannot run inside an active event loop; "
            "use `async for seg in transcribe_live(...)` instead."
        )
    agen = transcribe_live(source, backend=backend, vad=vad, **kwargs)
    loop = asyncio.new_event_loop()
    try:
        while True:
            try:
                yield loop.run_until_complete(agen.__anext__())
            except StopAsyncIteration:
                break
    finally:
        loop.run_until_complete(agen.aclose())   # propagate cancellation downstream
        loop.close()
```

Cost/benefit: this satisfies "simple things simple" for scripts and REPL use without
forking the engine into a sync+async pair (the rejected cost). The one caveat —
*don't call it from inside a live loop* — is enforced with an explicit error rather
than a deadlock, and documented in the docstring.

---

## 4. Package layout & symbol migration

### Target `scribed/` tree

```
scribed/
├── __init__.py        # +export: transcribe_live, iter_live, Transcriber, AudioSource,
│                      #          file_to_stream, from_mic, VAD, EnergyVAD, SileroVAD,
│                      #          segment_utterances, Channel
├── base.py            # ★ RESHAPED: frozen/slots, TimeSpan(int ms), Segment(+channel,+is_final), Word
├── streaming.py  NEW  # Transcriber + AudioSource Protocols; vad_segmented_stream; transcribe_live;
│                      #   file_to_stream; from_mic; AudioChunk
├── vad.py        NEW  # VAD Protocol, EnergyVAD, SileroVAD, segment_utterances, DEFAULT_*_MS  (← hearing)
├── audio.py      NEW  # to_mono, resample, to_mono_16k, rms_energy, load_audio, ffmpeg, STT_SAMPLE_RATE
├── make_backend.py    # +BaseTranscriberAdapter.transcribe_live default, _stream_native, natively_streams
│                      #  make_segment/make_word keep float-second start=/end=; convert to int-ms inside
├── registry.py        # unchanged — already capability-aware; reads natively_streams for 'stream'
├── services.py        # ServiceHandle gains .transcribe_live(source, **kwargs)
├── catalog.py, translation.py, credentials.py, install.py, status.py, tools.py, util.py, __main__.py
│                      # ~unchanged (tools.py JSON output edited: s.start -> s.span.start_ms)
├── testing.py    NEW  # FakeTranscriber, FakeStreamingTranscriber, tone/text fixtures, stream harness
├── backends/
│   ├── _template/     # +optional _stream_native example
│   ├── faster_whisper/ whisper/ openai/ elevenlabs/   # batch; stream FREE via VAD default
│   ├── vosk/          # +_stream_native (KaldiRecognizer.PartialResult); natively_streams=True
│   └── deepgram_live/ NEW  # native WS streaming; existing deepgram/ stays prerecorded-batch
└── data/backends.json # unchanged; 'streaming' flag now drives capability='stream' selection
```

### Symbol migration table

| Existing symbol / module | New home | Action |
|---|---|---|
| `scribed.base.{TimeSpan,Word,Segment,Transcript}` | `scribed/base.py` | **RESHAPE** → frozen/slots/int-ms/+channel/+is_final (breaking; §7 step 1) |
| `scribed.transcribe` / `transcribe_text` (sync batch) | `scribed/__init__.py` | **STAYS** (signatures unchanged) |
| `scribed.make_backend.BaseTranscriberAdapter` | `scribed/make_backend.py` | **+transcribe_live / _stream_native / natively_streams** (additive) |
| `scribed.make_segment` / `make_word` | `scribed/make_backend.py` | **KEEP float-second surface**; convert to int-ms internally; drop `level=` |
| `hearing.types.{TimeSpan,Word,TranscriptSegment,Transcript}` | re-export from `scribed.base` | **DELETE** local defs; `TranscriptSegment = scribed.base.Segment` alias |
| `hearing.types.{Channel,SpeakerLabel,ME,THEM,merge_segments,_ms_to_clock}` | `hearing/types.py` | **STAYS** (`Channel` re-exported from scribed) |
| `hearing.interfaces.STTEngine` | `scribed.streaming.Transcriber` | **DELETE**; hearing imports scribed's |
| `hearing.interfaces.{CaptureSource,Diarizer,AgentConsumer}` | `hearing/interfaces.py` | **STAYS** (app concerns) |
| `hearing.stt.FasterWhisperSTT` | `scribed/backends/faster_whisper/adapter.py` | **DELETE as dup** — port extras (`vad_filter`,`beam_size`) as `param_map` |
| `hearing.stt.OpenAISTT` | `scribed/backends/openai/adapter.py` | **DELETE as dup** |
| `hearing.stt.vad_stream_transcribe` | `scribed.streaming.vad_segmented_stream` | **MOVE + harden** (to_thread, resample, bounded in-flight) |
| `hearing.stt.{get_engine,default_engine}` | `scribed.services` / `get_default_backend` | **DELETE** the 2-branch factory; thin compat shim in hearing if needed |
| `hearing.stt._logprob_to_conf` | scribed backends already have it | **DELETE as dup** |
| `hearing.vad.*` | `scribed/vad.py` | **MOVE** (verified channel-agnostic) |
| `hearing.capture.{rms_energy,to_mono,resample,to_mono_16k,load_audio,_ffmpeg_decode_to_wav,STT_SAMPLE_RATE}` | `scribed/audio.py` | **MOVE** (generic conditioning) |
| `hearing.capture.StreamingFileCapture` | `scribed.streaming.file_to_stream` | **SUPERSEDE**; hearing keeps a thin channel-splitting wrapper |
| `hearing.capture.{split_channels,ChannelSplitFileCapture,DeviceCapture}` | `hearing/capture.py` | **STAYS** (mic/system + macOS BlackHole/Aggregate) |
| `hearing.pipeline.{transcribe,live_transcribe,summarize}` | `hearing/pipeline.py` | **STAYS** (rewired to scribed; queue fan-out unchanged) |
| `hearing.{diarize,agents,context,storage,http_app,cli}`, `frontend/*` | hearing | **STAYS** (pure app) |

**The de-duplication, explicit:** `hearing/stt.py` (~250 lines) collapses to either
nothing or a ~30-line compat shim. Both engine classes, `vad_stream_transcribe`,
`get_engine`, `default_engine`, and `_logprob_to_conf` are deleted; `hearing/vad.py`
is deleted (re-export shim during transition). The engines already exist in scribed —
this is genuinely deleting copies, not porting logic.

---

## 5. Progressive-disclosure surface

```python
import scribed

# (a) Transcribe a file — the one-liner, unchanged
t = scribed.transcribe("meeting.wav")              # -> Transcript
print(t.text)                                      # progressive disclosure: str sugar
print(t.srt)                                       # subtitle export
for seg in t:                                      # iterate Segments
    print(seg.span.start_ms, seg.speaker, seg.text)
text = scribed.transcribe_text("https://x/clip.mp3")   # -> str
```

```python
# (b) Transcribe live from the mic, with partials — the new one-liner
async for seg in scribed.transcribe_live(scribed.from_mic()):
    tag = "FINAL" if seg.is_final else "..."
    print(tag, seg.text)

# from a file as a simulated live stream (hardware-free; the CI harness):
src = scribed.file_to_stream("meeting.wav", block_ms=200, realtime=True)
async for seg in scribed.transcribe_live(src):
    print(seg.is_final, seg.text)

# ...and the SAME thing for non-async callers (scripts/REPL) — no `async` needed:
for seg in scribed.iter_live(scribed.from_mic()):
    print("FINAL" if seg.is_final else "...", seg.text)
```

```python
# (c) Swap engine — one keyword, batch OR stream
t = scribed.transcribe("call.wav", backend="deepgram", diarize=True)        # batch
async for seg in scribed.transcribe_live(src, backend="deepgram_live"):   # native WS streaming
    ...
async for seg in scribed.transcribe_live(src, backend="whisper",          # batch-only engine,
                                           vad=scribed.SileroVAD()):         #   auto VAD fallback
    ...

# Which engines stream natively (true interim partials) vs finals-only?
scribed.list_backends(capability="stream")     # registry, capability-aware
scribed.find(streaming="yes", is_local=True)   # ledger filter
```

```python
# (d) Add a backend — unchanged two-file scaffold; streaming is optional and FREE if omitted
from scribed.make_backend import scaffold_backend, validate_adapter, validate_stream
scaffold_backend("assemblyai")                 # generates config.py + adapter.py from the ledger

# adapter.py:
class Adapter(BaseTranscriberAdapter):
    def _transcribe(self, audio, **native_kwargs) -> Transcript: ...     # REQUIRED (batch)
    # OPTIONAL native streaming; omit it and the engine streams for free via VAD fallback:
    natively_streams = True
    async def _stream_native(self, source, *, vad=None, **kw) -> AsyncIterator[Segment]: ...

validate_adapter("assemblyai")                 # batch smoke test (tone or speech clip)
validate_stream("assemblyai")                  # streaming smoke test via file_to_stream (no hardware)
```

---

## 6. What hearing becomes

hearing is now a clean meeting-**app** that composes scribed + diarization + agents +
UI. It declares a dependency on `scribed`.

- **`hearing/stt.py`** → deleted (or a ~30-line compat shim). `get_engine(name)`
  becomes a thin map onto `scribed.services[…]`; `default_engine()` returns the
  scribed faster-whisper handle. No engine SDK code, no VAD wrapper.
- **`hearing/vad.py`** → deleted; `from scribed.vad import VAD, EnergyVAD, SileroVAD,
  segment_utterances`.
- **`hearing/capture.py`** → slimmed to the **channel layer only**: `split_channels`,
  `ChannelSplitFileCapture`, `DeviceCapture` (BlackHole/Aggregate). Generic helpers
  import from `scribed.audio`. A `CaptureSource` yields `(Channel, chunk)`; hearing
  demuxes each channel into a `scribed.AudioSource` and feeds it to
  `scribed.transcribe_live`.
- **`hearing/types.py`** → thin: `TranscriptSegment = scribed.base.Segment`, plus
  re-exports of `Transcript`/`TimeSpan`/`Word`/`Channel` from scribed, plus
  hearing-only `SpeakerLabel`/`ME`/`THEM`/`merge_segments`/`_ms_to_clock`. Because
  `Channel` is a first-class field on the unified `Segment`,
  `ChannelTrickDiarizer.assign_speakers` (reads `seg.channel`, writes
  `seg.with_speaker`) and `merge_segments` (sorts by `span.start_ms`) work unchanged.
- **`hearing/pipeline.py`** → stays, rewired. `transcribe()` calls
  `scribed.transcribe` per channel, stamps `Channel`, `merge_segments`, applies
  `ChannelTrickDiarizer`/agent. `live_transcribe()` keeps the per-channel
  `asyncio.Queue` fan-out, supervisor, sentinels, and drop policy; each
  `_stt_for_channel` task now drives `scribed.transcribe_live(channel_source,
  backend=…)` and filters `seg.is_final` (was `seg.meta['final']`).
- **`hearing/{diarize,agents,context,storage,http_app,cli}`** and the React
  frontend → unchanged in substance.

**Frontend HTTP contract — preserved by construction.** Because scribed's `Segment`
now *is* the int-ms/frozen/`channel`-bearing type, `http_app.segment_to_dict` reads
`seg.span.start_ms`, `seg.channel`, `seg.speaker`, and now `seg.is_final` (one-line
change from `seg.meta['final']`), projecting to the camelCase `SegmentSchema` with
**no wire-format change and no float→int rounding**. One caveat to verify (§7):
`storage.transcript_from_json` hardcodes its field set and may drop `words`/`meta` on
round-trip — confirm `is_final` survives or is defaulted correctly.

---

## 7. Migration plan (ordered, incremental, test-first)

This adopts minimal-seam's **additive-first, engine-flip-last** discipline (the
migration judge's strong recommendation) while reaching full-centralization's unified
spine — but the breaking base-type reshape is an *explicitly approved, test-rewritten*
step, never bundled with the engine move. The maintainer's "never break existing
tests without asking" rule governs: before each gate, the named tests must be green;
the one deliberate break (step 1) requires maintainer sign-off and a lockstep test
rewrite.

**Shared testability primitives built first (step 0):**

- `scribed/testing.py`: `FakeTranscriber` (returns a canned `Transcript` from text,
  no model) and `FakeStreamingTranscriber` (yields scripted interim+final
  `Segment`s), mirroring hearing's `FakeSTT`/`FakeStreamingSTT` culture. These let
  every pipeline/streaming test run with **no model and no network**.
- The hardware-free stream harness is `file_to_stream(..., realtime=False)`;
  `segment_utterances` is unit-testable standalone with synthetic energy frames.
- An `importorskip`-gated real-STT smoke test (macOS `say` → faster-whisper),
  mirrored from hearing into scribed, so the real recognition path has one
  green-on-laptop end-to-end test (auto-skipped in CI — a known gap, see §8).

**Ordered steps:**

1. **★ APPROVED BREAK — reshape `scribed/base.py` to the unified frozen/int-ms
   spine.** Add `channel`, `is_final`; switch `Word`/`Segment` to `span: TimeSpan`;
   drop `level`/`LEVELS`. Keep `make_segment`/`make_word` float-second surface; route
   conversion through `TimeSpan.from_seconds`. **Own the enumerated breakage:**
   rewrite `tests/test_scribed.py` (the assertions pinning `TimeSpan(1.0,3.5)
   .duration`/`.as_tuple`/`from_tuple`, flat `Word(start=)`/`Segment(start=)`,
   `t.segments == []` list-vs-tuple, `from_text(duration=…)`, `level`), fix
   `tools.py` JSON output (`s.start` → `s.span.start_ms`), the SRT/VTT formatter
   (`span.as_seconds`), and `make_backend.validate_adapter`'s `has_timing` check
   (`s.start` → `s.span`). **Gate:** full scribed batch suite green +
   `validate_adapter` smoke passes for all installed backends before/after.
   *Riskiest in scribed; de-risk by doing it atomically behind the rewritten tests,
   with maintainer sign-off, in its own PR.*

2. **Move generic audio + VAD into scribed.** Create `scribed/audio.py` and
   `scribed/vad.py` (+`rms_energy`). Port hearing's VAD tests verbatim. **Gate:** new
   `scribed/vad.py` unit tests green (`segment_utterances` on synthetic frames;
   `EnergyVAD` threshold behavior). *Low risk — pure functions, channel-agnostic.*

3. **Add the streaming seam (additive).** `streaming.py`: `Transcriber`/`AudioSource`
   Protocols, `vad_segmented_stream` (with `to_thread` + resample + bounded
   in-flight), `file_to_stream`, `from_mic`, `transcribe_live`;
   `BaseTranscriberAdapter.transcribe_live`/`_stream_native`/`natively_streams`;
   `ServiceHandle.transcribe_live`; registry `capability='stream'` selection.
   **Gate:** streaming tests using `FakeStreamingTranscriber` and `file_to_stream`
   against faster-whisper (no hardware); an explicit **long-stream offset-accuracy
   test** (multi-minute synthetic stream; assert absolute spans don't drift and are
   monotonic); a head-of-line test (slow fake decode + fast VAD; assert bounded
   in-flight). *Medium risk — concurrency + timestamp correctness.*

4. **Build one native streamer (`deepgram_live`).** Implement `_stream_native` with
   an internal bounded queue bridging the server-push WS to the consumer-pull
   generator, reconciling interim/final by message id. **Gate:**
   `validate_stream("deepgram_live")` (interim-before-final contract enforced); gated
   behind credential presence so CI without keys skips it. *Medium risk — real WS,
   billed; gate hard.*

5. **★ RISKY — repoint hearing onto scribed.** Introduce the scribed-backed engine
   path alongside the old one *first* (compat shim), then flip
   `get_engine`/`default_engine`/`_default_engine`. Delete `hearing/stt.py` engines,
   `hearing/vad.py`; slim `capture.py`; make `types.py` re-export `scribed.base`
   (`TranscriptSegment = Segment`); rewire `pipeline.py` (`_stt_for_channel` →
   `transcribe_live`; `meta['final']` → `is_final`); edit
   `http_app.segment_to_dict` (`is_final`). **Gate:** confirm a root-level `hearing`
   integration test exercises `transcribe`/`summarize`/`live_transcribe` *before*
   flipping — if missing, **write it and flag to the maintainer first** (per the
   no-break rule). Then the full hearing suite green. *Highest risk — type-coupling
   fan-out across diarize/agents/storage/http; de-risk by keeping `Channel` a
   first-class field so existing channel assertions need no rewrite.*

6. **Verify the frontend contract end-to-end.** `storage.transcript_from_json`
   round-trip (confirm `is_final` survives); `segment_to_dict` output diffed
   byte-for-byte against the pre-migration shape; run `hearing serve`, hit
   `/api/transcribe` and `/api/transcribe/stream`, confirm Zod validation passes
   unchanged in the React UI. **Gate:** golden-file diff on the NDJSON payload + a
   live browser smoke check. *Medium risk — silent-then-loud Zod failures.*

7. **Delete dead code; migrate docs/skills.** Remove transition shims once imports
   are updated. Move the `hearing-stt` / `hearing-live-pipeline` skill content
   (a "scribed design document in the wrong package") into scribed skills. **Gate:**
   no remaining imports of deleted symbols (`rg` sweep); docs build.

8. **(Post-migration, incremental) native vosk streaming + concurrency hardening.**
   Add vosk `_stream_native` (`PartialResult`); add the registry-concurrency test
   (§8) before declaring streaming production-ready for concurrent sessions.

---

## 8. Open questions for the maintainer

1. ✅ **RESOLVED** (see *Decisions locked*) — async canonical **+ a thin sync
   `iter_live` driver** (§3.4). Not async-only.

2. ✅ **RESOLVED** — yes, scribed gets generic `from_mic()` + `file_to_stream()`;
   macOS `DeviceCapture` + channel-split stay in hearing.

3. ✅ **RESOLVED** — int-ms frozen reshape accepted as a signed-off step-1 break;
   `hearing` depends on `scribed`. (Still to *do*, not to *decide*: confirm via `rg`
   that no other current scribed consumer pins the float/mutable shape.)

4. ✅ **RESOLVED** — `channel: Optional[Channel] = None` is a first-class field on
   scribed's `Segment`.

5. ▶ **RECOMMENDED (adopting unless you object)** — **a shared `scribed.streaming`
   push→pull bridge helper**, not a per-adapter queue. Deepgram-live's WS pushes
   finals regardless of consumer backpressure, so the bridge owns the bounded buffer,
   sentinel-on-close, socket teardown on cancellation, SDK-callback exception
   surfacing, and the interim-before-final contract — code too subtle to duplicate
   per backend. It exposes `feed()` and a `feed_threadsafe()` (via
   `loop.call_soon_threadsafe`) because several SDKs call back from a background
   thread. Each native adapter then only maps *native payload → Segment* and wires
   `on_message → bridge.feed`.

6. ▶ **RECOMMENDED (adopting unless you object)** — guard `_discover_backends` with a
   module `threading.Lock` and set `_discovered = True` **after** the scan completes
   (it is currently set *before* — `registry.py:41-42` — a latent bug: once
   `to_thread` decode workers exist, a second thread can observe `_discovered=True`
   and use an empty/partial registry). Keep the cheap documented invariant "discovery
   runs at first facade call"; no per-session registry needed.

7. ✅ **RESOLVED** — headline async verb `transcribe_live` (over `transcribe_stream`);
   sync pair `iter_live`; public Protocol `Transcriber` + internal `Adapter` both
   kept; fallback `vad_segmented_stream`.

---

## 9. Rejected alternatives

- **minimal-seam (Stance A) — keep two type systems, bridge per-segment.** Rejected
  as the *permanent* design: it institutionalizes the exact duplication the refactor
  exists to remove, pays a per-segment translation tax forever, and creates a
  standing open-closed violation (a scribed field rename silently drops data through
  the hand-kept bridge). **What we kept:** its migration *posture* — purely additive
  scribed changes first, engine flip last and gated, an isolated round-trip test at
  the type seam, and the `scribed/testing.py` hardware-free stream harness.

- **full-centralization (Stance B) — batteries-included, audio sources +
  `StreamConfig`/`pipeline` module in scribed core.** Rejected in its *shape*: the
  `realtime/` subpackage with nested `StreamConfig`/`VADConfig` is more named OOP
  structure than the capability needs. More seriously, its streaming model *stacks
  two backpressure regimes* (a drop-oldest queue inside scribed under hearing's
  blocking fan-out), which silently drops audio. **What we kept:** the *type model* —
  the unified frozen/int-ms spine owned by scribed, and `Channel` as a first-class
  `Optional` field.

- **protocol-first (Stance C) — two verbs, one engine, channel in `meta`.** Adopted
  as the *abstraction spine* (the architecture-purist winner): required `transcribe`
  + optional `transcribe_live`, framework-synthesized VAD fallback, async-generator
  composition with no orchestrator class, `is_final` as a true typed field, and the
  explicit `asyncio.to_thread` offload. **What we rejected:** exiling `Channel` to
  `Segment.meta['channel']` — a self-inflicted inconsistency that recreates the very
  fragility it fixes for `is_final`.

**Net synthesis:** protocol-first's two-verbs/one-engine composable-stream design +
full-centralization's unified frozen int-ms spine with first-class `Optional[Channel]`
+ minimal-seam's incremental test-first migration ordering — with the one-time
breaking base reshape explicitly budgeted and approved, the streaming fallback
hardened (offloaded + bounded + resampled) beyond what any source code does today,
and scribed's backpressure boundary stated honestly rather than oversold.
