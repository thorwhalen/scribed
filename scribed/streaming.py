"""Real-time (streaming) transcription: live audio in, :class:`Segment`\\ s out.

This is the symmetric twin of scribed's batch facade. Where ``scribed.transcribe``
turns a whole file into a :class:`~scribed.base.Transcript`, ``transcribe_live``
turns a live :class:`AudioSource` into an async stream of
:class:`~scribed.base.Segment`\\ s, each flagged ``is_final`` (interim hypotheses
have ``is_final=False``; finalized utterances ``True``).

Two adaptation paths satisfy ONE interface:

* **Native streaming** — a backend that talks a live protocol (e.g. a Deepgram
  WebSocket, Vosk's ``PartialResult``) implements ``_stream_native`` and emits true
  interim partials. (Not yet shipped; the hook is in :mod:`scribed.make_backend`.)
* **Synthesized fallback** — any batch-only engine streams *for free* via
  :func:`vad_segmented_stream`: VAD groups audio into utterances, each is
  transcribed off the event loop (``asyncio.to_thread``) and emitted as a finalized
  segment. Latency ≈ trailing-silence + decode; finals only, no interim partials.

The consumer never picks the path — :func:`transcribe_live` resolves a backend and
routes transparently. Async generators are the canonical surface; :func:`iter_live`
is a thin synchronous driver for non-async callers. This module needs numpy and is
imported lazily, so plain ``import scribed`` stays light.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from typing import (
    Any,
    AsyncIterator,
    Iterator,
    Optional,
    Protocol,
    Union,
    runtime_checkable,
)

import numpy as np

from scribed.audio import (
    STT_SAMPLE_RATE,
    load_audio,
    to_mono,
    to_mono_16k,
    to_wav_bytes,
)
from scribed.base import AudioChunk, AudioInput, Segment, Transcript
from scribed.vad import VAD, segment_utterances


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class Transcriber(Protocol):
    """A speech-to-text engine. Batch ``transcribe`` is required; live is optional."""

    def transcribe(self, audio: AudioInput, **kwargs: Any) -> Transcript:
        """Whole input -> complete :class:`~scribed.base.Transcript`."""
        ...

    def transcribe_live(
        self, source: "AudioSource", *, vad: Optional[VAD] = None, **kwargs: Any
    ) -> AsyncIterator[Segment]:
        """Live audio -> async stream of :class:`~scribed.base.Segment`\\ s.

        Optional: if a backend does not implement it, the framework synthesizes it
        from ``transcribe`` via :func:`vad_segmented_stream`.
        """
        ...


@runtime_checkable
class AudioSource(Protocol):
    """A real-time audio source: an async-iterable of mono float32 chunks.

    Channel-agnostic on purpose — multi-channel / "me vs them" routing is the
    consumer's job (feed one :class:`AudioSource` per channel).
    """

    sample_rate: int

    def __aiter__(self) -> AsyncIterator[AudioChunk]: ...


# ---------------------------------------------------------------------------
# Audio sources
# ---------------------------------------------------------------------------


@dataclass
class _ArrayStream:
    """An :class:`AudioSource` over an in-memory mono waveform, chunked by time."""

    mono: np.ndarray
    sample_rate: int
    block_ms: int = 200
    realtime: bool = False

    def __aiter__(self) -> AsyncIterator[AudioChunk]:
        return self._stream()

    async def _stream(self) -> AsyncIterator[AudioChunk]:
        block = max(1, int(self.block_ms / 1000 * self.sample_rate))
        for start in range(0, len(self.mono), block):
            blk = self.mono[start : start + block]
            if blk.size:
                yield blk
            if self.realtime:
                await asyncio.sleep(self.block_ms / 1000)


def file_to_stream(
    audio: Union[AudioInput, np.ndarray],
    *,
    block_ms: int = 200,
    realtime: bool = False,
    sample_rate: Optional[int] = None,
) -> AudioSource:
    """Turn a file / bytes / array into a simulated live :class:`AudioSource`.

    The hardware-free harness for the whole streaming path: a file is decoded and
    down-mixed to mono at its native rate and replayed in ``block_ms`` chunks
    (``realtime=True`` paces with ``asyncio.sleep`` for demos; the default streams
    as fast as possible, for tests).

    Args:
        audio: a path/URL, WAV ``bytes``, or a numpy waveform. For a raw array you
            must pass ``sample_rate``.
        block_ms: chunk size in milliseconds.
        realtime: pace playback in real time (demos) vs. as-fast-as-possible (tests).
        sample_rate: required only when ``audio`` is a numpy array.
    """
    mono, sr = _to_mono_source(audio, sample_rate)
    return _ArrayStream(mono=mono, sample_rate=sr, block_ms=block_ms, realtime=realtime)


def _to_mono_source(
    audio: Union[AudioInput, np.ndarray], sample_rate: Optional[int]
) -> tuple[np.ndarray, int]:
    """Resolve any supported input to ``(mono_float32, sample_rate)``."""
    if isinstance(audio, np.ndarray):
        if sample_rate is None:
            raise ValueError("sample_rate is required when passing a numpy array.")
        return to_mono(audio), int(sample_rate)
    if isinstance(audio, (bytes, bytearray)):
        import io

        import soundfile as sf

        data, sr = sf.read(io.BytesIO(bytes(audio)), dtype="float32", always_2d=True)
        return to_mono(data), int(sr)
    # str path/URL or Path
    data, sr = load_audio(audio)
    return to_mono(data), int(sr)


def from_mic(
    *,
    device: Optional[Union[int, str]] = None,
    block_ms: int = 200,
    sample_rate: int = STT_SAMPLE_RATE,
) -> AudioSource:
    """A generic single-device microphone :class:`AudioSource` (lazy ``sounddevice``).

    This is the *generic* mic — one device, mono. Multi-source meeting capture
    (mic + system audio on an aggregate device) is a consumer concern, not scribed's.
    Needs ``pip install 'scribed[mic]'``.
    """
    return _MicStream(device=device, block_ms=block_ms, sample_rate=sample_rate)


@dataclass
class _MicStream:
    """An :class:`AudioSource` reading mono blocks from an input device."""

    device: Optional[Union[int, str]] = None
    block_ms: int = 200
    sample_rate: int = STT_SAMPLE_RATE

    def __aiter__(self) -> AsyncIterator[AudioChunk]:
        return self._stream()

    async def _stream(self) -> AsyncIterator[AudioChunk]:  # pragma: no cover - hardware
        try:
            import sounddevice as sd
        except ImportError as e:
            raise ImportError(
                "from_mic() needs sounddevice. Install with: pip install 'scribed[mic]'\n"
                "For a hardware-free run, use scribed.file_to_stream(...)."
            ) from e
        loop = asyncio.get_event_loop()
        block = max(1, int(self.block_ms / 1000 * self.sample_rate))
        with sd.InputStream(
            device=self.device,
            channels=1,
            samplerate=self.sample_rate,
            dtype="float32",
            blocksize=block,
        ) as stream:
            while True:
                data, _overflowed = await loop.run_in_executor(None, stream.read, block)
                yield to_mono(np.asarray(data))


# ---------------------------------------------------------------------------
# The synthesized streaming fallback
# ---------------------------------------------------------------------------


async def vad_segmented_stream(
    engine: Union[Transcriber, Any],
    source: AudioSource,
    *,
    vad: Optional[VAD] = None,
    target_rate: int = STT_SAMPLE_RATE,
    max_inflight: int = 1,
    **kwargs: Any,
) -> AsyncIterator[Segment]:
    """Make a non-streaming engine stream: VAD-segment audio, batch-transcribe each.

    Each VAD-finalized utterance is down-mixed/resampled to ``target_rate`` mono,
    encoded as WAV ``bytes``, and handed to the engine's batch ``transcribe`` **off
    the event loop** (``asyncio.to_thread``) — so a slow local decode never stalls
    capture. Spans are offset to absolute stream time; segments are finalized
    (``is_final=True``) — this path emits no interim partials.

    ``max_inflight`` caps concurrent decodes while preserving emission order (a
    bounded look-ahead): ``1`` (default) is strict serial; higher values let a short
    decode pool absorb bursts of back-to-back utterances at the cost of memory.
    """
    sr = int(getattr(source, "sample_rate", target_rate))
    transcribe = engine.transcribe if hasattr(engine, "transcribe") else engine
    max_inflight = max(1, int(max_inflight))

    async def _decode(utterance: np.ndarray, start_ms: int) -> list[Segment]:
        wav = to_wav_bytes(to_mono_16k(utterance, sr, target=target_rate), target_rate)
        transcript = await asyncio.to_thread(lambda: transcribe(wav, **kwargs))
        return [seg.offset(start_ms) for seg in transcript.segments]

    pending: "deque[asyncio.Task]" = deque()
    try:
        async for utterance, start_ms in segment_utterances(
            source, sample_rate=sr, vad=vad
        ):
            pending.append(asyncio.create_task(_decode(utterance, start_ms)))
            if len(pending) >= max_inflight:
                for seg in await pending.popleft():
                    yield seg
        while pending:
            for seg in await pending.popleft():
                yield seg
    finally:
        for task in pending:
            task.cancel()


# ---------------------------------------------------------------------------
# The facade (async) + a thin synchronous driver
# ---------------------------------------------------------------------------


async def transcribe_live(
    source: AudioSource,
    *,
    backend: Optional[str] = None,
    vad: Optional[VAD] = None,
    **kwargs: Any,
) -> AsyncIterator[Segment]:
    """Stream :class:`~scribed.base.Segment`\\ s from a live :class:`AudioSource`.

    Resolves a backend (the default transcribe backend unless ``backend=`` is given)
    and routes to its live path: a native streamer if the adapter implements one,
    else the synthesized VAD fallback. Every batch backend therefore streams.

        async for seg in scribed.transcribe_live(scribed.from_mic()):
            print("FINAL" if seg.is_final else "...", seg.text)
    """
    import scribed

    name = backend or scribed.get_default_backend()
    adapter = scribed.services[name].adapter
    native = getattr(adapter, "transcribe_live", None)
    agen = (
        native(source, vad=vad, **kwargs)
        if native is not None
        else vad_segmented_stream(adapter, source, vad=vad, **kwargs)
    )
    async for seg in agen:
        yield seg


def iter_live(
    source: AudioSource,
    *,
    backend: Optional[str] = None,
    vad: Optional[VAD] = None,
    **kwargs: Any,
) -> Iterator[Segment]:
    """Synchronous driver over :func:`transcribe_live` for non-async callers.

        for seg in scribed.iter_live(scribed.from_mic()):
            print("FINAL" if seg.is_final else "...", seg.text)

    Runs the async stream on a private event loop and yields each Segment to a plain
    ``for``. MUST NOT be called from inside a running event loop (use the async
    ``transcribe_live`` there) — it raises a clear error if it detects one.
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
        loop.run_until_complete(agen.aclose())
        loop.close()
