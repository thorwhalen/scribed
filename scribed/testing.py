"""Model-free test doubles and fixtures for the streaming/batch surfaces.

Real STT engines need models, weights, or network; these fakes let the pipeline,
the VAD-segmented fallback, and the live facade be tested deterministically with
**no model, no network, no audio hardware**:

- :class:`FakeTranscriber` — a batch :class:`~scribed.streaming.Transcriber` that
  ignores the audio and returns canned text. Drop it into ``vad_segmented_stream``
  (or register it as a backend) to exercise the fallback plumbing.
- :class:`FakeStreamingTranscriber` — a *native* streamer that yields scripted
  interim + final segments, for testing ``is_final`` handling and native routing.
- :func:`speech_silence_stream` — a synthetic :class:`~scribed.streaming.AudioSource`
  of loud bursts separated by silence, which :class:`~scribed.vad.EnergyVAD`
  segments into a known number of utterances.

Importing this module pulls numpy (it builds waveforms); it is a *test/dev* helper,
not part of the runtime import surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional, Sequence, Tuple

import numpy as np

from scribed.base import Segment, TimeSpan, Transcript
from scribed.streaming import AudioSource, file_to_stream


@dataclass
class FakeTranscriber:
    """A model-free batch ``Transcriber``: returns canned text, ignores the audio.

    Each ``transcribe`` call returns the next string from ``texts`` (cycling) as a
    single-segment :class:`~scribed.base.Transcript` spanning ``[0, seg_duration_s)``.
    Deterministic under serial decoding (the default ``max_inflight=1``).
    """

    texts: Sequence[str] = ("hello world",)
    backend: str = "fake"
    seg_duration_s: float = 1.0
    calls: int = field(default=0, init=False)

    def transcribe(self, audio: Any, **kwargs: Any) -> Transcript:
        text = self.texts[self.calls % len(self.texts)]
        self.calls += 1
        seg = Segment(text, span=TimeSpan.from_seconds(0.0, self.seg_duration_s))
        return Transcript.from_segments([seg], backend=self.backend)


@dataclass
class FakeStreamingTranscriber:
    """A model-free *native* streamer: yields scripted ``(text, is_final)`` segments.

    Exercises the native-streaming path and ``is_final`` propagation without any
    live protocol. Also satisfies the batch contract (returns the last final text).
    """

    script: Sequence[Tuple[str, bool]] = (("hel", False), ("hello", True))
    backend: str = "fake-stream"
    natively_streams: bool = True

    def transcribe(self, audio: Any, **kwargs: Any) -> Transcript:
        finals = [t for t, is_final in self.script if is_final]
        return Transcript.from_text(finals[-1] if finals else "", backend=self.backend)

    async def transcribe_live(
        self, source: AudioSource, *, vad: Optional[Any] = None, **kwargs: Any
    ) -> AsyncIterator[Segment]:
        async for _block in source:  # drain the source so it is actually exercised
            pass
        t_ms = 0
        for text, is_final in self.script:
            yield Segment(text, span=TimeSpan(t_ms, t_ms + 500), is_final=is_final)
            if is_final:
                t_ms += 500


def speech_silence_stream(
    *,
    n_utterances: int = 2,
    sample_rate: int = 16_000,
    speech_ms: int = 500,
    silence_ms: int = 900,
    block_ms: int = 100,
    amplitude: float = 0.3,
    freq: float = 220.0,
) -> AudioSource:
    """Build a synthetic :class:`AudioSource` of ``n_utterances`` speech bursts.

    Each burst is a ``speech_ms`` sine tone (loud enough for
    :class:`~scribed.vad.EnergyVAD`) followed by ``silence_ms`` of silence (long
    enough — > the VAD's 700 ms default — to finalize a turn). EnergyVAD therefore
    segments the stream into exactly ``n_utterances`` utterances. Deterministic; no
    file, no hardware.
    """
    n_speech = int(sample_rate * speech_ms / 1000)
    n_silence = int(sample_rate * silence_ms / 1000)
    t = np.arange(n_speech) / sample_rate
    burst = (amplitude * np.sin(2 * np.pi * freq * t)).astype("float32")
    gap = np.zeros(n_silence, dtype="float32")
    waveform = np.concatenate(
        [np.concatenate([burst, gap]) for _ in range(n_utterances)]
    )
    return file_to_stream(waveform, sample_rate=sample_rate, block_ms=block_ms)
