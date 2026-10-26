"""Adapter for the WhisperX backend (transcribe -> align -> optionally diarize).

Pipeline, on a float32 mono 16 kHz array (no ffmpeg needed):

1. ``whisperx.load_model(model, device, compute_type=...)`` (cached) then
   ``.transcribe(audio, batch_size=..., language=...)``;
2. if ``align``: ``whisperx.load_align_model`` + ``whisperx.align`` for accurate
   word timestamps;
3. if ``diarize``: pyannote via WhisperX's ``DiarizationPipeline`` +
   ``whisperx.assign_word_speakers`` (needs a Hugging Face token, env ``HF_TOKEN``).

The result is openai-whisper-shaped, mapped by
:func:`scribed.backends._whisper_common.whisper_result_to_segments`. ``whisperx`` (and ``torch``,
for device auto-detection) are imported on first use.
"""

from __future__ import annotations

import importlib
import inspect
import warnings

from scribed.base import Transcript
from scribed.make_backend import BaseTranscriberAdapter

from scribed.backends._whisper_common import (
    require_module,
    to_waveform_16k,
    whisper_result_to_segments,
)
from scribed.backends.whisperx.config import DEFAULT_MODEL, HF_TOKEN_ENV_VARS

#: ``compute_type`` used when none is given, by device.
DEFAULT_COMPUTE_TYPES = {"cuda": "float16", "cpu": "int8"}


def _auto_device() -> str:
    """``"cuda"`` if torch sees a GPU, else ``"cpu"``."""
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _hf_token() -> str:
    """The Hugging Face token pyannote diarization needs, or an informative error."""
    from scribed.credentials import resolve_credential

    token = resolve_credential(env_var=list(HF_TOKEN_ENV_VARS), required=False)
    if not token:
        raise RuntimeError(
            "WhisperX diarization (diarize=True) needs a Hugging Face token: set "
            f"{' or '.join(HF_TOKEN_ENV_VARS)}, after accepting the pyannote "
            "speaker-diarization model terms on huggingface.co. Or transcribe "
            "with diarize=False and use a separate diarizer."
        )
    return token


class Adapter(BaseTranscriberAdapter):
    """WhisperX adapter (caches ASR, alignment and diarization models)."""

    #: Engine module name — the seam tests use to inject a fake backend.
    module_name = "whisperx"

    def __init__(self, config: dict):
        super().__init__(config)
        self._cache: dict = {}

    def _cached(self, key, make):
        if key not in self._cache:
            self._cache[key] = make()
        return self._cache[key]

    def _diarization_pipeline(self, wx, device: str):
        cls = getattr(wx, "DiarizationPipeline", None)
        if cls is None:  # whisperx >= 3.4 keeps it in a submodule
            cls = importlib.import_module(
                f"{self.module_name}.diarize"
            ).DiarizationPipeline
        # whisperx renamed the token argument (``use_auth_token`` up to 3.4,
        # ``token`` by 3.8); pass whichever this install's pipeline takes.
        try:
            params = inspect.signature(cls).parameters
        except (TypeError, ValueError):
            params = {}
        key = "use_auth_token" if "use_auth_token" in params else "token"
        return cls(**{key: _hf_token()}, device=device)

    def _transcribe(
        self,
        audio,
        *,
        model=DEFAULT_MODEL,
        language=None,
        diarize=False,
        align=True,
        batch_size=16,
        device=None,
        compute_type=None,
        min_speakers=None,
        max_speakers=None,
        **native_kwargs,
    ) -> Transcript:
        wx = require_module(self.module_name, engine=self.backend_id, extra="whisperx")
        device = device or _auto_device()
        compute_type = compute_type or DEFAULT_COMPUTE_TYPES.get(device, "default")
        waveform = to_waveform_16k(audio)

        asr = self._cached(
            ("asr", model, device, compute_type, language),
            lambda: wx.load_model(
                model, device, compute_type=compute_type, language=language
            ),
        )
        result = asr.transcribe(
            waveform, batch_size=batch_size, language=language, **native_kwargs
        )
        detected = result.get("language") or language

        if align and result.get("segments") and detected:
            try:
                align_model, metadata = self._cached(
                    ("align", detected, device),
                    lambda: wx.load_align_model(language_code=detected, device=device),
                )
            except ValueError as exc:  # no default align model for this language
                warnings.warn(
                    f"whisperx: no word alignment for {detected!r} ({exc}); "
                    "returning the unaligned segments",
                    stacklevel=2,
                )
                align = False
        if align and result.get("segments") and detected:
            result = wx.align(
                result["segments"],
                align_model,
                metadata,
                waveform,
                device,
                return_char_alignments=False,
            )

        if diarize:
            pipeline = self._cached(
                ("diarize", device), lambda: self._diarization_pipeline(wx, device)
            )
            turns = pipeline(
                waveform, min_speakers=min_speakers, max_speakers=max_speakers
            )
            result = wx.assign_word_speakers(turns, result)

        return Transcript.from_segments(
            whisper_result_to_segments(result),
            backend=self.backend_id,
            raw=result,
            language=detected,
        )
