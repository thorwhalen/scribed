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
  nested word-level :class:`Word` units.
- :class:`Word` — a single word with its own time span (when the engine reports
  word-level timestamps).
- :class:`TimeSpan` — a ``[start, end]`` interval in seconds; the temporal analog
  of a bounding box.

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

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, List, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# Input type
# ---------------------------------------------------------------------------

# Audio input accepted by all facade functions. The string forms cover both a
# filesystem path and an ``http(s)://`` URL; ``bytes`` is raw encoded audio
# data; the file-like and numpy forms are quoted because they are decoded lazily
# in ``scribed.util`` and must never be imported at module load time.
AudioInput = Union[str, Path, bytes, "BinaryIO", "NDArray"]  # noqa: F821

# Transcription granularity levels, coarse -> fine. This is the canonical
# ordering used for sorting and filtering. Diarized speaker turns are carried on
# the ``speaker`` field of a segment rather than as a separate level.
LEVELS: Tuple[str, ...] = ("transcript", "segment", "word")


# ---------------------------------------------------------------------------
# Time geometry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TimeSpan:
    """A ``[start, end]`` interval in seconds (the temporal analog of a box).

    ``start`` and ``end`` are floats measured in seconds from the beginning of
    the audio. The temporal analog of ocracy's ``BBox``.
    """

    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def as_tuple(self) -> Tuple[float, float]:
        """``(start, end)`` in seconds."""
        return (self.start, self.end)

    @classmethod
    def from_tuple(cls, span: Any) -> "TimeSpan":
        start, end = span
        return cls(start=float(start), end=float(end))


# ---------------------------------------------------------------------------
# Text units
# ---------------------------------------------------------------------------


@dataclass
class Word:
    """A single recognized word, with its own time span when available.

    Attributes:
        text: The recognized word.
        start: Start time in seconds, if the backend reports word timestamps.
        end: End time in seconds, if available.
        confidence: Recognition confidence in ``[0, 1]`` (normalized by scribed
            from whatever scale the backend used), if available.
        speaker: Speaker label for this word, if diarized at word level.
    """

    text: str
    start: Optional[float] = None
    end: Optional[float] = None
    confidence: Optional[float] = None
    speaker: Optional[str] = None

    def __str__(self) -> str:
        return self.text

    @property
    def span(self) -> Optional[TimeSpan]:
        if self.start is None or self.end is None:
            return None
        return TimeSpan(self.start, self.end)


@dataclass
class Segment:
    """One recognized span of speech (an utterance / chunk).

    The main structured unit, analogous to ocracy's ``TextBlock``. A diarized
    speaker turn is just a segment whose ``speaker`` is set.

    Attributes:
        text: The recognized text for this span.
        start: Start time in seconds, if the backend reports timestamps.
        end: End time in seconds, if available.
        confidence: Recognition confidence in ``[0, 1]`` (normalized), if any.
        speaker: Speaker label (e.g. ``"A"``, ``"speaker_0"``) when diarized.
        language: Detected/declared language code for this span, if any.
        level: Granularity — one of :data:`LEVELS` ("segment" by default).
        words: Word-level units when the backend reports word timestamps.
        meta: Backend-specific extras (avg_logprob, no_speech_prob, ...).
    """

    text: str
    start: Optional[float] = None
    end: Optional[float] = None
    confidence: Optional[float] = None
    speaker: Optional[str] = None
    language: Optional[str] = None
    level: str = "segment"
    words: List[Word] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return self.text

    @property
    def span(self) -> Optional[TimeSpan]:
        if self.start is None or self.end is None:
            return None
        return TimeSpan(self.start, self.end)


# ---------------------------------------------------------------------------
# The normalized result
# ---------------------------------------------------------------------------


@dataclass
class Transcript:
    """The normalized result of transcribing audio with any backend.

    ``text`` is the headline payload: the full transcript in time order.
    ``segments`` carries the structured spans (with times/speakers/confidences)
    when the backend provides them. ``raw`` is the untouched backend output.
    ``meta`` holds cross-cutting extras (model, timing, ...).

    Progressive disclosure::

        t = scribed.transcribe("talk.mp3")
        print(t)                 # -> the transcript text
        t.text                   # -> the same string
        for seg in t:            # -> iterate Segments
            print(seg.start, seg.speaker, seg.text)
        t.words                  # -> flattened word-level units
        t.speakers               # -> sorted speaker labels (if diarized)
        t.srt                    # -> SRT subtitles
        t.vtt                    # -> WebVTT subtitles
        t.raw                    # -> engine-specific structure
    """

    text: str
    segments: List[Segment] = field(default_factory=list)
    backend: str = ""
    language: Optional[str] = None
    duration: Optional[float] = None
    raw: Any = None
    meta: dict = field(default_factory=dict)

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

    # -- subtitle export (the ASR analog of ocracy's .markdown) -------------
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
            segments=kept,
            backend=self.backend,
            language=self.language,
            duration=self.duration,
            raw=self.raw,
            meta=dict(self.meta),
        )

    # -- constructors -------------------------------------------------------
    @classmethod
    def from_text(
        cls, text: str, *, backend: str = "", raw: Any = None, **meta: Any
    ) -> "Transcript":
        """Build a minimal result from just a text string (no timing)."""
        language = meta.pop("language", None)
        duration = meta.pop("duration", None)
        return cls(
            text=text,
            backend=backend,
            language=language,
            duration=duration,
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
        **meta: Any,
    ) -> "Transcript":
        """Build a result from structured segments.

        If ``text`` is not given it is synthesized by joining the segments' text
        in their given order with ``joiner`` (callers should pass segments
        already in time order, or pre-join and pass ``text`` explicitly).
        """
        if text is None:
            text = joiner.join(s.text.strip() for s in segments).strip()
        return cls(
            text=text,
            segments=list(segments),
            backend=backend,
            language=language,
            duration=duration,
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
