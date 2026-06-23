"""Adapter for the OpenAI transcription backend.

Maps scribed's normalized request onto ``client.audio.transcriptions.create`` and
the response onto a :class:`scribed.base.Transcript`. The client and credential
are resolved lazily so ``import scribed`` stays dependency-free.
"""

from __future__ import annotations

import math

from scribed.base import Transcript
from scribed.make_backend import BaseTranscriberAdapter, make_segment


def _get(obj, key):
    """Read ``key`` from a pydantic-ish object or a plain dict."""
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


class Adapter(BaseTranscriberAdapter):
    """OpenAI transcription adapter."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            from scribed.credentials import resolve_credential

            key = resolve_credential(
                "openai", env_var=self.config.get("api_env_var") or None, required=True
            )
            self._client = OpenAI(api_key=key)
        return self._client

    def _transcribe(self, audio, *, model="whisper-1", **native_kwargs) -> Transcript:
        from scribed.util import cleanup_temp, ensure_file_path

        client = self._get_client()
        # whisper-1 supports verbose_json (segments); gpt-4o models do not.
        verbose = not str(model).startswith("gpt-4o")
        path, is_temp = ensure_file_path(audio, suffix=".wav")
        try:
            with open(path, "rb") as fh:
                create_kwargs = dict(model=model, file=fh, **native_kwargs)
                if verbose:
                    create_kwargs["response_format"] = "verbose_json"
                resp = client.audio.transcriptions.create(**create_kwargs)
        finally:
            cleanup_temp(path, is_temp)

        text = _get(resp, "text") or ""
        language = _get(resp, "language")
        duration = _get(resp, "duration")
        raw_segments = _get(resp, "segments")

        if raw_segments:
            segments = []
            for s in raw_segments:
                alp = _get(s, "avg_logprob")
                conf = math.exp(alp) if isinstance(alp, (int, float)) else None
                segments.append(
                    make_segment(
                        _get(s, "text") or "",
                        start=_get(s, "start"),
                        end=_get(s, "end"),
                        confidence=conf,
                        avg_logprob=alp,
                        no_speech_prob=_get(s, "no_speech_prob"),
                    )
                )
            return Transcript.from_segments(
                segments,
                backend=self.backend_id,
                raw=resp,
                text=text,
                language=language,
                duration=duration,
            )

        return Transcript.from_text(
            text,
            backend=self.backend_id,
            raw=resp,
            language=language,
            duration=duration,
        )
