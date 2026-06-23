"""Adapter for the whisper.cpp backend (via the ``pywhispercpp`` binding).

Maps scribed's normalized request onto :class:`pywhispercpp.model.Model` and its
native ``Segment`` stream onto a :class:`scribed.base.Transcript`. The engine is
imported and the model constructed lazily so ``import scribed`` stays
dependency-free; one ``Model`` is cached per requested size on the adapter.

whisper.cpp reports segment timestamps in *centiseconds* (1/100th of a second),
so ``seg.t0`` / ``seg.t1`` are divided by 100 to get seconds. There are no
per-word timestamps by default; a per-segment confidence (the geometric mean of
token probabilities, in ``[0, 1]``) is surfaced when whisper.cpp computes it.
"""

from __future__ import annotations

import math
import os

from scribed.base import Transcript
from scribed.make_backend import BaseTranscriberAdapter, make_segment


def _segment_confidence(seg):
    """Return ``seg.probability`` as a ``[0, 1]`` confidence, or ``None``.

    whisper.cpp only fills ``probability`` when probability extraction is on; it
    is ``NaN`` otherwise. ``make_segment`` clamps to ``[0, 1]`` but cannot read a
    ``NaN``, so guard it here.
    """
    prob = getattr(seg, "probability", None)
    if prob is None:
        return None
    try:
        prob = float(prob)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(prob) else prob


class Adapter(BaseTranscriberAdapter):
    """whisper.cpp adapter (caches one model per requested size)."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._model_size = os.environ.get("SCRIBED_WHISPERCPP_MODEL", "base")
        self._models: dict = {}

    def _get_model(self, model_size: str):
        from pywhispercpp.model import Model

        if model_size not in self._models:
            # Downloads the ggml weights for this size on first construction.
            self._models[model_size] = Model(model_size)
        return self._models[model_size]

    def _transcribe(self, audio, *, model=None, **native_kwargs) -> Transcript:
        from scribed.util import cleanup_temp, ensure_file_path

        engine = self._get_model(model or self._model_size)

        # whisper.cpp uses "" (not None) for auto-detect; drop an empty language.
        if not native_kwargs.get("language"):
            native_kwargs.pop("language", None)

        path, is_temp = ensure_file_path(audio)
        try:
            try:
                # extract_probability=True populates each segment's confidence;
                # older pywhispercpp bindings may not accept the kwarg.
                segments = engine.transcribe(
                    path, extract_probability=True, **native_kwargs
                )
            except TypeError:
                segments = engine.transcribe(path, **native_kwargs)
        finally:
            cleanup_temp(path, is_temp)

        out = [
            make_segment(
                (getattr(seg, "text", "") or "").strip(),
                start=getattr(seg, "t0", 0) / 100.0,
                end=getattr(seg, "t1", 0) / 100.0,
                confidence=_segment_confidence(seg),
            )
            for seg in segments
        ]

        return Transcript.from_segments(out, backend=self.backend_id, raw=segments)
