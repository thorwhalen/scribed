"""Adapter for the Groq (hosted Whisper) transcription backend.

Groq's audio-transcriptions API mirrors OpenAI's, so this adapter is a close
sibling of :mod:`scribed.backends.openai.adapter`: it maps scribed's normalized
request onto ``client.audio.transcriptions.create`` and the ``verbose_json``
response onto a :class:`scribed.base.Transcript`. The Groq SDK and credential
are resolved lazily so ``import scribed`` stays dependency-free, and the audio is
sent as a ``(filename, bytes)`` tuple via :func:`scribed.util.load_audio_bytes`.
"""

from __future__ import annotations

import math

from scribed.base import Transcript
from scribed.make_backend import BaseTranscriberAdapter, make_segment


def _get(obj, key):
    """Read ``key`` from a pydantic-ish object or a plain dict."""
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


class Adapter(BaseTranscriberAdapter):
    """Groq hosted-Whisper transcription adapter (client cached lazily)."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from groq import Groq

            from scribed.credentials import resolve_credential

            key = resolve_credential(
                "groq", env_var=self.config.get("api_env_var") or None, required=True
            )
            self._client = Groq(api_key=key)
        return self._client

    def _transcribe(
        self, audio, *, model="whisper-large-v3-turbo", **native_kwargs
    ) -> Transcript:
        from scribed.util import load_audio_bytes

        client = self._get_client()
        audio_bytes = load_audio_bytes(audio)
        resp = client.audio.transcriptions.create(
            file=("audio.wav", audio_bytes),
            model=model,
            response_format="verbose_json",
            **native_kwargs,
        )

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
