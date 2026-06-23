"""Adapter for the OpenAI Whisper (PyTorch) backend.

Maps scribed's normalized request onto ``whisper.load_model(...).transcribe(...)``
and the resulting result-dict onto a :class:`scribed.base.Transcript`. The engine
and model are imported and constructed lazily so ``import scribed`` stays
dependency-free.

The reference Whisper decodes audio with a system ``ffmpeg`` and expects a real
file path, so in-memory inputs are first materialized via
:func:`scribed.util.ensure_file_path` (and cleaned up afterwards).
"""

from __future__ import annotations

import math
import os

from scribed.base import Transcript
from scribed.make_backend import BaseTranscriberAdapter, make_segment, make_word


def _logprob_to_conf(avg_logprob):
    """Map Whisper's average log-probability to a rough ``[0, 1]`` confidence."""
    if avg_logprob is None:
        return None
    try:
        return math.exp(float(avg_logprob))  # avg_logprob <= 0 => exp in (0, 1]
    except (TypeError, ValueError, OverflowError):
        return None


class Adapter(BaseTranscriberAdapter):
    """OpenAI Whisper (PyTorch) adapter (caches one model per requested size)."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._model_size = os.environ.get("SCRIBED_WHISPER_MODEL", "base")
        self._models: dict = {}

    def _get_model(self, model_size: str):
        import whisper

        if model_size not in self._models:
            self._models[model_size] = whisper.load_model(model_size)
        return self._models[model_size]

    def _transcribe(self, audio, *, model=None, **native_kwargs) -> Transcript:
        from scribed.util import cleanup_temp, ensure_file_path

        engine = self._get_model(model or self._model_size)
        path, is_temp = ensure_file_path(audio)
        try:
            result = engine.transcribe(path, **native_kwargs)
        finally:
            cleanup_temp(path, is_temp)

        segments = []
        for seg in result.get("segments", []):
            words = [
                make_word(
                    w["word"],
                    start=w.get("start"),
                    end=w.get("end"),
                    confidence=w.get("probability"),
                )
                for w in seg.get("words", [])
            ]
            segments.append(
                make_segment(
                    seg["text"],
                    start=seg["start"],
                    end=seg["end"],
                    confidence=_logprob_to_conf(seg.get("avg_logprob")),
                    words=words,
                    avg_logprob=seg.get("avg_logprob"),
                    no_speech_prob=seg.get("no_speech_prob"),
                )
            )

        return Transcript.from_segments(
            segments,
            backend=self.backend_id,
            raw=result,
            language=result.get("language"),
        )
