"""Adapter for the mlx-whisper backend (Whisper on Apple Silicon via MLX).

Decodes the input to a float32 mono 16 kHz array (no ffmpeg needed), calls
``mlx_whisper.transcribe(array, path_or_hf_repo=...)`` and maps its
openai-whisper-shaped result dict onto a :class:`scribed.base.Transcript`.
``mlx_whisper`` is imported on first use, after the Apple-Silicon check, so this
module imports anywhere.
"""

from __future__ import annotations

from typing import Optional

from scribed.base import Transcript
from scribed.make_backend import BaseTranscriberAdapter

from scribed.backends._whisper_common import (
    require_apple_silicon,
    require_module,
    to_waveform_16k,
    whisper_result_to_segments,
)
from scribed.backends.mlx_whisper.config import DEFAULT_MODEL

#: How a bare Whisper size maps to an ``mlx-community`` repo id.
MODEL_REPO_TEMPLATE = "mlx-community/whisper-{model}-mlx"

#: Sizes whose mlx-community repo does not follow :data:`MODEL_REPO_TEMPLATE`.
MODEL_REPO_OVERRIDES = {
    "turbo": "mlx-community/whisper-large-v3-turbo",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
}


def resolve_model_repo(model: Optional[str]) -> str:
    """Resolve a model name to a Hugging Face repo id for ``mlx_whisper``.

    >>> resolve_model_repo("base")
    'mlx-community/whisper-base-mlx'
    >>> resolve_model_repo("turbo")
    'mlx-community/whisper-large-v3-turbo'
    >>> resolve_model_repo("someone/custom-whisper")
    'someone/custom-whisper'
    """
    if not model:
        return DEFAULT_MODEL
    if "/" in model:
        return model
    return MODEL_REPO_OVERRIDES.get(model, MODEL_REPO_TEMPLATE.format(model=model))


class Adapter(BaseTranscriberAdapter):
    """mlx-whisper adapter (Apple Silicon only)."""

    #: Engine module name — the seam tests use to inject a fake backend.
    module_name = "mlx_whisper"

    def _engine(self):
        require_apple_silicon(self.backend_id)
        return require_module(self.module_name, engine=self.backend_id, extra="mlx")

    def _transcribe(
        self, audio, *, model=DEFAULT_MODEL, language=None, **native_kwargs
    ) -> Transcript:
        mlx_whisper = self._engine()
        result = mlx_whisper.transcribe(
            to_waveform_16k(audio),
            path_or_hf_repo=resolve_model_repo(model),
            language=language,
            **native_kwargs,
        )
        return Transcript.from_segments(
            whisper_result_to_segments(result),
            backend=self.backend_id,
            raw=result,
            text=(result.get("text") or "").strip() or None,
            language=result.get("language") or language,
        )
