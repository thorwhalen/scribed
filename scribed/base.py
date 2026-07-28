"""Core types and normalized result objects for scribed.

Speech-to-text (ASR) engines disagree wildly on what they return: local Whisper
emits a list of timestamped segments; cloud APIs return nested JSON of
utterances/words with speaker labels and confidences; some engines return only a
plain string. scribed normalizes all of that into a small, stable set of
dataclasses so that callers get the *same shape* regardless of which backend
produced the transcript:

- :class:`Transcript` — the full result of transcribing audio: a concatenated
  ``text`` (in time order) plus a list of structured ``segments`` carrying time
  spans, speakers and confidences, plus the untouched ``raw`` backend output for
  power users who need engine-specific detail.
- :class:`Segment` — one recognized span of speech (an utterance / chunk) with an
  optional :class:`TimeSpan`, ``speaker`` (when diarized), ``confidence`` and
  nested word-level :class:`Word` units. Optionally an ``is_final`` flag (live
  streaming) and a capture ``channel`` (multi-source capture, e.g. mic vs system).
- :class:`Word` — a single word with its own time span (when the engine reports
  word-level timestamps).
- :class:`TimeSpan` — a ``[start_ms, end_ms)`` half-open interval in **integer
  milliseconds**; the temporal analog of a bounding box.

**Time is integer milliseconds, by design.** A transcript is *standoff interval
annotation* over the audio: segments reference the audio by time and never carry
the samples. Integer-millisecond time is accumulation-safe (offsetting a live
stream's spans never drifts), hashable, and round-trippable to a wire format. For
ergonomics, :class:`Word`/:class:`Segment` also expose read-only ``start``/``end``
**float-second** convenience accessors derived from ``span`` — but ``span`` (in ms)
is the single source of truth.

The result dataclasses are **frozen** (immutable): a concern enriches a segment by
*copying* (``with_speaker`` / ``with_channel`` / :func:`dataclasses.replace`), never
by mutating in place.

The input side is normalized too: every facade function accepts an
:data:`AudioInput` — a path, URL, ``bytes``, file-like object, or numpy waveform.
Concrete decoding happens lazily in :mod:`scribed.util`, so importing scribed
never requires soundfile or numpy.

The design goal is *progressive disclosure*: ``str(transcript)`` gives you the
text, ``transcript.text`` is the same string, iterating yields its segments,
``transcript.srt`` / ``transcript.vtt`` give you subtitles, and
``transcript.segments`` / ``transcript.raw`` are there when you need structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Iterator, List, Mapping, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# Input type
# ---------------------------------------------------------------------------

# Audio input accepted by all batch facade functions. The string forms cover both
# a filesystem path and an ``http(s)://`` URL; ``bytes`` is raw encoded audio
# data; the file-like and numpy forms are quoted because they are decoded lazily
# in ``scribed.util`` and must never be imported at module load time.
AudioInput = Union[str, "Path", bytes, "BinaryIO", "NDArray"]  # noqa: F821

# A single block of real-time audio: a 1-D float32 mono waveform (decoded). Used
# by the streaming surface; quoted for the same lazy-import reason as above.
AudioChunk = "NDArray"  # noqa: F821


# ---------------------------------------------------------------------------
# Capture provenance (optional; meaningful to multi-source consumers)
# ---------------------------------------------------------------------------


class Channel(str, Enum):
    """Which capture channel a segment came from (optional, ``None`` for generic STT).

    Generic single-source transcription leaves :attr:`Segment.channel` as ``None``.
    Multi-source consumers (e.g. a meeting recorder capturing the microphone and
    the system output separately) stamp the channel so "who spoke" survives all the
    way down: :attr:`MIC` is the local user, :attr:`SYSTEM` is everyone else,
    :attr:`MIXED` is a single/unknown source.
    """

    MIC = "mic"
    SYSTEM = "system"
    MIXED = "mixed"


# ---------------------------------------------------------------------------
# Time geometry
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TimeSpan:
    """A half-open ``[start_ms, end_ms)`` interval in **integer milliseconds**.

    Integer time — never bare float seconds — so it is accumulation-safe (offsetting
    a live stream's spans never accrues float drift), hashable, and round-trippable.
    The temporal analog of a bounding box.

    >>> TimeSpan(0, 1500).duration_ms
    1500
    >>> TimeSpan.from_seconds(1.0, 3.5).as_seconds
    (1.0, 3.5)
    """

    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        """Length of the interval in milliseconds (clamped at 0)."""
        return max(0, self.end_ms - self.start_ms)

    @property
    def as_seconds(self) -> Tuple[float, float]:
        """``(start, end)`` in float seconds (the format/subtitle boundary)."""
        return (self.start_ms / 1000.0, self.end_ms / 1000.0)

    @classmethod
    def from_seconds(cls, start: float, end: float) -> "TimeSpan":
        """Build a span from float seconds (e.g. from an STT engine's output)."""
        return cls(int(round(start * 1000)), int(round(end * 1000)))

    def offset(self, by_ms: int) -> "TimeSpan":
        """Return a copy shifted later by ``by_ms`` (e.g. to absolute stream time)."""
        return TimeSpan(self.start_ms + by_ms, self.end_ms + by_ms)


# ---------------------------------------------------------------------------
# Text units
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Word:
    """A single recognized word, with its own :class:`TimeSpan` when available.

    Attributes:
        text: The recognized word.
        span: The word's time span (ms), if the backend reports word timestamps.
        confidence: Recognition confidence in ``[0, 1]`` (normalized by scribed
            from whatever scale the backend used), if available.
        speaker: Speaker label for this word, if diarized at word level.
    """

    text: str
    span: Optional[TimeSpan] = None
    confidence: Optional[float] = None
    speaker: Optional[str] = None

    def __str__(self) -> str:
        return self.text

    @property
    def start(self) -> Optional[float]:
        """Start time in **float seconds** (convenience), or ``None`` if untimed."""
        return None if self.span is None else self.span.start_ms / 1000.0

    @property
    def end(self) -> Optional[float]:
        """End time in **float seconds** (convenience), or ``None`` if untimed."""
        return None if self.span is None else self.span.end_ms / 1000.0


@dataclass(frozen=True, slots=True)
class Segment:
    """One recognized span of speech (an utterance / chunk).

    The main structured unit. A diarized speaker turn is just a segment whose
    ``speaker`` is set. Frozen — enrich by copying (``with_speaker`` /
    ``with_channel`` / :func:`dataclasses.replace`), never mutate.

    Attributes:
        text: The recognized text for this span.
        span: The segment's time span (ms), if the backend reports timestamps.
        confidence: Recognition confidence in ``[0, 1]`` (normalized), if any.
        speaker: Speaker label (e.g. ``"A"``, ``"speaker_0"``) when diarized.
        language: Detected/declared language code for this span, if any.
        channel: Capture provenance (mic/system/...) for multi-source consumers;
            ``None`` for generic single-source transcription.
        is_final: ``True`` for a finalized segment (always so for batch); a live
            streaming engine sets ``False`` on interim (partial) hypotheses.
        words: Word-level units when the backend reports word timestamps.
        meta: Backend-specific extras (avg_logprob, no_speech_prob, engine, ...).
    """

    text: str
    span: Optional[TimeSpan] = None
    confidence: Optional[float] = None
    speaker: Optional[str] = None
    language: Optional[str] = None
    channel: Optional[Channel] = None
    is_final: bool = True
    words: Tuple[Word, ...] = ()
    meta: Mapping[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.text

    @property
    def start(self) -> Optional[float]:
        """Start time in **float seconds** (convenience), or ``None`` if untimed."""
        return None if self.span is None else self.span.start_ms / 1000.0

    @property
    def end(self) -> Optional[float]:
        """End time in **float seconds** (convenience), or ``None`` if untimed."""
        return None if self.span is None else self.span.end_ms / 1000.0

    def with_speaker(self, speaker: str) -> "Segment":
        """Return a copy carrying a speaker label (frozen -> copy, don't mutate)."""
        return replace(self, speaker=speaker)

    def with_channel(self, channel: Channel) -> "Segment":
        """Return a copy carrying a capture-channel label (frozen -> copy)."""
        return replace(self, channel=channel)

    def offset(self, by_ms: int) -> "Segment":
        """Return a copy with ``span`` shifted later by ``by_ms`` (absolute time)."""
        if self.span is None:
            return self
        return replace(self, span=self.span.offset(by_ms))


# ---------------------------------------------------------------------------
# The normalized result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Transcript:
    """The normalized result of transcribing audio with any backend.

    ``text`` is the headline payload: the full transcript in time order.
    ``segments`` carries the structured spans (with times/speakers/confidences)
    when the backend provides them. ``raw`` is the untouched backend output.
    ``meta`` holds cross-cutting extras (model, timing, ...).

    Frozen: build via :meth:`from_text` / :meth:`from_segments` or the constructor;
    derive variants with :meth:`with_meta` / :meth:`filter_confidence`.

    Progressive disclosure::

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
    """

    text: str
    segments: Tuple[Segment, ...] = ()
    backend: str = ""
    language: Optional[str] = None
    duration: Optional[float] = None  # total audio duration, in seconds
    sample_rate: Optional[int] = None
    raw: Any = None
    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Accept any sequence of segments; normalize to a tuple (frozen -> setattr).
        if not isinstance(self.segments, tuple):
            object.__setattr__(self, "segments", tuple(self.segments))

    # -- string / iteration sugar ------------------------------------------
    def __str__(self) -> str:
        return self.text

    def __len__(self) -> int:
        return len(self.text)

    def __iter__(self) -> Iterator[Segment]:
        return iter(self.segments)

    def __bool__(self) -> bool:
        return bool(self.text.strip()) or bool(self.segments)

    # -- structured views ---------------------------------------------------
    @property
    def duration_ms(self) -> Optional[int]:
        """Total duration in milliseconds (convenience), or ``None`` if unknown."""
        return None if self.duration is None else int(round(self.duration * 1000))

    @property
    def words(self) -> List[Word]:
        """All word-level units, flattened across segments (may be empty)."""
        return [w for seg in self.segments for w in seg.words]

    @property
    def speakers(self) -> List[str]:
        """Sorted distinct speaker labels across segments (empty if undiarized)."""
        return sorted({seg.speaker for seg in self.segments if seg.speaker})

    def at_speaker(self, speaker: str) -> List[Segment]:
        """Segments attributed to a given speaker."""
        return [seg for seg in self.segments if seg.speaker == speaker]

    @property
    def mean_confidence(self) -> Optional[float]:
        """Mean confidence over segments that report one, or ``None``."""
        confs = [s.confidence for s in self.segments if s.confidence is not None]
        return sum(confs) / len(confs) if confs else None

    def with_meta(self, **kw: Any) -> "Transcript":
        """Return a copy with extra metadata merged in (frozen -> copy)."""
        return replace(self, meta={**dict(self.meta), **kw})

    # -- subtitle export ----------------------------------------------------
    @property
    def srt(self) -> str:
        """SRT subtitles built from timed segments (empty string if untimed)."""
        return self.as_srt()

    @property
    def vtt(self) -> str:
        """WebVTT subtitles built from timed segments (empty string if untimed)."""
        return self.as_vtt()

    def as_srt(self) -> str:
        """Render timed segments as SubRip (.srt). Segments without times are skipped."""
        lines: List[str] = []
        i = 0
        for seg in self.segments:
            if seg.start is None or seg.end is None:
                continue
            i += 1
            speaker = f"[{seg.speaker}] " if seg.speaker else ""
            lines.append(str(i))
            lines.append(
                f"{_format_timestamp(seg.start, comma=True)} --> "
                f"{_format_timestamp(seg.end, comma=True)}"
            )
            lines.append(f"{speaker}{seg.text.strip()}")
            lines.append("")
        return "\n".join(lines)

    def as_vtt(self) -> str:
        """Render timed segments as WebVTT (.vtt). Segments without times are skipped."""
        lines: List[str] = ["WEBVTT", ""]
        for seg in self.segments:
            if seg.start is None or seg.end is None:
                continue
            speaker = f"<v {seg.speaker}>" if seg.speaker else ""
            lines.append(
                f"{_format_timestamp(seg.start, comma=False)} --> "
                f"{_format_timestamp(seg.end, comma=False)}"
            )
            lines.append(f"{speaker}{seg.text.strip()}")
            lines.append("")
        return "\n".join(lines)

    def filter_confidence(self, min_confidence: float) -> "Transcript":
        """Return a copy keeping only segments at or above ``min_confidence``.

        Segments without a confidence are dropped. ``text`` is rebuilt from the
        surviving segments.
        """
        kept = [
            s
            for s in self.segments
            if s.confidence is not None and s.confidence >= min_confidence
        ]
        return Transcript(
            text=" ".join(s.text.strip() for s in kept),
            segments=tuple(kept),
            backend=self.backend,
            language=self.language,
            duration=self.duration,
            sample_rate=self.sample_rate,
            raw=self.raw,
            meta=dict(self.meta),
        )

    # -- constructors -------------------------------------------------------
    @classmethod
    def from_text(
        cls, text: str, *, backend: str = "", raw: Any = None, **meta: Any
    ) -> "Transcript":
        """Build a minimal result from just a text string (no timing/segments)."""
        language = meta.pop("language", None)
        duration = meta.pop("duration", None)
        sample_rate = meta.pop("sample_rate", None)
        return cls(
            text=text,
            backend=backend,
            language=language,
            duration=duration,
            sample_rate=sample_rate,
            raw=raw,
            meta=meta,
        )

    @classmethod
    def from_segments(
        cls,
        segments: List[Segment],
        *,
        backend: str = "",
        raw: Any = None,
        text: Optional[str] = None,
        joiner: str = " ",
        language: Optional[str] = None,
        duration: Optional[float] = None,
        sample_rate: Optional[int] = None,
        **meta: Any,
    ) -> "Transcript":
        """Build a result from structured segments.

        If ``text`` is not given it is synthesized by joining the segments' text
        in their given order with ``joiner`` (callers should pass segments
        already in time order, or pre-join and pass ``text`` explicitly).
        """
        segments = list(segments)
        if text is None:
            text = joiner.join(s.text.strip() for s in segments).strip()
        return cls(
            text=text,
            segments=tuple(segments),
            backend=backend,
            language=language,
            duration=duration,
            sample_rate=sample_rate,
            raw=raw,
            meta=meta,
        )


def _format_timestamp(seconds: float, *, comma: bool = True) -> str:
    """Format ``seconds`` as ``HH:MM:SS,mmm`` (SRT) or ``HH:MM:SS.mmm`` (VTT)."""
    if seconds < 0:
        seconds = 0.0
    millis = int(round(seconds * 1000.0))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    sep = "," if comma else "."
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{millis:03d}"
