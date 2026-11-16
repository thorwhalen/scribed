"""Adapter for the Groq (hosted Whisper) transcription backend.

Groq's audio-transcriptions API mirrors OpenAI's, so this adapter is a close
sibling of :mod:`scribed.backends.openai.adapter`: it maps scribed's normalized
request onto ``client.audio.transcriptions.create`` and the ``verbose_json``
response onto a :class:`scribed.base.Transcript`. The Groq SDK and credential
are resolved lazily so ``import scribed`` stays dependency-free, and the audio is
sent as a ``(filename, bytes)`` tuple via :func:`scribed.util.load_audio_bytes`.
"""

from __future__ import annotations

from scribed.backends._verbose_json import verbose_json_to_transcript
from scribed.base import Transcript
from scribed.make_backend import BaseTranscriberAdapter


class Adapter(BaseTranscriberAdapter):
    """Groq hosted-Whisper transcription adapter (client cached lazily)."""

    accepts_api_key = True

    def __init__(self, config: dict):
        super().__init__(config)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from groq import Groq

            key = self.credential()
            self._client = Groq(api_key=key)
        return self._client

    def _create(
        self, *, model="whisper-large-v3-turbo", timestamp_granularities=None, **source
    ) -> Transcript:
        """One ``audio.transcriptions.create`` call; ``source`` is ``file=`` or ``url=``."""
        extra = {"timestamp_granularities": timestamp_granularities}
        resp = self._get_client().audio.transcriptions.create(
            model=model,
            response_format="verbose_json",
            **{k: v for k, v in extra.items() if v},
            **source,
        )
        return verbose_json_to_transcript(resp, backend_id=self.backend_id)

    def _transcribe(self, audio, **native_kwargs) -> Transcript:
        from scribed.util import load_audio_bytes

        file = ("audio.wav", load_audio_bytes(audio))
        return self._create(file=file, **native_kwargs)

    def _transcribe_url(self, url: str, **native_kwargs) -> Transcript:
        """Groq fetches ``url`` itself (its ``url`` field; no 25 MB upload limit)."""
        return self._create(url=url, **native_kwargs)
