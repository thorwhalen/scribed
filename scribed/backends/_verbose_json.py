"""Shared mapping of an OpenAI-style ``verbose_json`` response onto a ``Transcript``.

OpenAI's and Groq's audio-transcription endpoints answer in the same shape:
``text``, ``language``, ``duration``, a ``segments`` list (``start``, ``end``,
``text``, ``avg_logprob``, ``no_speech_prob``) and, when word timestamps were
requested (``timestamp_granularities=["word", "segment"]``), a **top-level**
``words`` list (``word``, ``start``, ``end``) that is not nested in the segments.
This module owns that mapping, including attaching each word to its segment.
"""

from __future__ import annotations

import math
import bisect
from typing import Any, List

from scribed.base import Transcript
from scribed.make_backend import make_segment, make_word


def _get(obj: Any, key: str) -> Any:
    """Read ``key`` from a pydantic-ish object or a plain dict."""
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def _word(raw: Any):
    return make_word(
        (_get(raw, "word") or "").strip(),
        start=_get(raw, "start"),
        end=_get(raw, "end"),
    )


def _words_by_segment(raw_words, spans) -> List[list]:
    """Give each word to the segment whose span holds its start (else the nearest earlier one)."""
    buckets: List[list] = [[] for _ in spans]
    starts = [s if s is not None else float("inf") for s, _ in spans]  # ascending
    for raw in raw_words:
        word = _word(raw)
        if not word.text or word.span is None or not buckets:
            continue
        index = max(
            0, bisect.bisect_right(starts, word.span.start_ms / 1000.0 + 1e-9) - 1
        )
        buckets[index].append(word)
    return buckets


def verbose_json_to_transcript(resp: Any, *, backend_id: str) -> Transcript:
    """Map a ``verbose_json`` response (object or dict) onto a :class:`Transcript`."""
    text = _get(resp, "text") or ""
    language = _get(resp, "language")
    duration = _get(resp, "duration")
    raw_segments = _get(resp, "segments")
    raw_words = _get(resp, "words") or []
    common = dict(backend=backend_id, raw=resp, language=language, duration=duration)

    if raw_segments:
        spans = [(_get(s, "start"), _get(s, "end")) for s in raw_segments]
        words = _words_by_segment(raw_words, spans)
        segments = []
        for s, segment_words in zip(raw_segments, words):
            alp = _get(s, "avg_logprob")
            segments.append(
                make_segment(
                    _get(s, "text") or "",
                    start=_get(s, "start"),
                    end=_get(s, "end"),
                    confidence=math.exp(alp) if isinstance(alp, (int, float)) else None,
                    words=segment_words,
                    avg_logprob=alp,
                    no_speech_prob=_get(s, "no_speech_prob"),
                )
            )
        return Transcript.from_segments(segments, text=text, **common)

    if raw_words:  # words without segments: one segment holding them all
        words = [w for w in map(_word, raw_words) if w.text]
        segment = make_segment(
            text,
            start=words[0].span.start_ms / 1000.0 if words and words[0].span else None,
            end=words[-1].span.end_ms / 1000.0 if words and words[-1].span else None,
            words=words,
        )
        return Transcript.from_segments([segment], text=text, **common)

    return Transcript.from_text(text, **common)
