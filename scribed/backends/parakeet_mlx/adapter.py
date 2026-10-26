"""Adapter for the parakeet-mlx backend (NVIDIA Parakeet-TDT on Apple Silicon).

Loads a model with ``parakeet_mlx.from_pretrained(repo)`` (cached per repo),
transcribes a temporary audio file, and maps the returned ``AlignedResult``'s
sentences (text + float-second ``start``/``end``) onto scribed segments.
Parakeet's tokens are sub-word pieces, so no word list is emitted.
``parakeet_mlx`` is imported on first use, after the Apple-Silicon check.
"""

from __future__ import annotations

from scribed.base import Transcript
from scribed.make_backend import BaseTranscriberAdapter, make_segment

from scribed.backends._whisper_common import require_apple_silicon, require_module
from scribed.backends.parakeet_mlx.config import DEFAULT_MODEL


class Adapter(BaseTranscriberAdapter):
    """parakeet-mlx adapter (Apple Silicon only; caches one model per repo)."""

    #: Engine module name — the seam tests use to inject a fake backend.
    module_name = "parakeet_mlx"

    def __init__(self, config: dict):
        super().__init__(config)
        self._models: dict = {}

    def _model(self, repo: str):
        require_apple_silicon(self.backend_id)
        if repo not in self._models:
            parakeet = require_module(
                self.module_name, engine=self.backend_id, extra="mlx"
            )
            self._models[repo] = parakeet.from_pretrained(repo)
        return self._models[repo]

    def _transcribe(self, audio, *, model=DEFAULT_MODEL, **native_kwargs) -> Transcript:
        from scribed.util import audio_path

        engine = self._model(model or DEFAULT_MODEL)
        with audio_path(audio) as path:
            result = engine.transcribe(path, **native_kwargs)
        segments = [
            make_segment(
                (getattr(s, "text", "") or "").strip(),
                start=getattr(s, "start", None),
                end=getattr(s, "end", None),
            )
            for s in (getattr(result, "sentences", None) or [])
        ]
        return Transcript.from_segments(
            segments,
            backend=self.backend_id,
            raw=result,
            text=(getattr(result, "text", "") or "").strip() or None,
        )
