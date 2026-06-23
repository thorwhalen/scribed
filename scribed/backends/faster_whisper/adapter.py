"""Adapter for the faster-whisper backend.

Maps scribed's normalized request onto :class:`faster_whisper.WhisperModel` and
its native ``Segment``/``Word`` stream onto a :class:`scribed.base.Transcript`.
The engine and model are imported and constructed lazily so ``import scribed``
stays dependency-free.
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
    """faster-whisper adapter (caches one model per requested size)."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._model_size = os.environ.get("SCRIBED_FASTER_WHISPER_MODEL", "base")
        self._device = os.environ.get("SCRIBED_FASTER_WHISPER_DEVICE", "auto")
        self._compute_type = os.environ.get("SCRIBED_FASTER_WHISPER_COMPUTE", "default")
        self._models: dict = {}

    def _get_model(self, model_size: str):
        from faster_whisper import WhisperModel

        if model_size not in self._models:
            self._models[model_size] = WhisperModel(
                model_size, device=self._device, compute_type=self._compute_type
            )
        return self._models[model_size]

    def _transcribe(self, audio, *, model=None, **native_kwargs) -> Transcript:
        from scribed.util import cleanup_temp, ensure_file_path

        engine = self._get_model(model or self._model_size)
        path, is_temp = ensure_file_path(audio)
        try:
            seg_iter, info = engine.transcribe(path, **native_kwargs)
            segments = []
            for s in seg_iter:  # generator — consumed inside the temp-file lifetime
                words = [
                    make_word(
                        w.word,
                        start=w.start,
                        end=w.end,
                        confidence=getattr(w, "probability", None),
                    )
                    for w in (getattr(s, "words", None) or [])
                ]
                segments.append(
                    make_segment(
                        s.text,
                        start=s.start,
                        end=s.end,
                        confidence=_logprob_to_conf(getattr(s, "avg_logprob", None)),
                        words=words,
                        avg_logprob=getattr(s, "avg_logprob", None),
                        no_speech_prob=getattr(s, "no_speech_prob", None),
                    )
                )
        finally:
            cleanup_temp(path, is_temp)

        return Transcript.from_segments(
            segments,
            backend=self.backend_id,
            raw=info,
            language=getattr(info, "language", None),
            duration=getattr(info, "duration", None),
        )
