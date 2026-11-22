"""Adapter for the OpenAI transcription backend.

Maps scribed's normalized request onto ``client.audio.transcriptions.create`` and
the response onto a :class:`scribed.base.Transcript`. The client and credential
are resolved lazily so ``import scribed`` stays dependency-free.
"""

from __future__ import annotations

import warnings

from scribed.backends._verbose_json import verbose_json_to_transcript
from scribed.base import Transcript
from scribed.make_backend import BaseTranscriberAdapter
from scribed.registry import has_capability


class Adapter(BaseTranscriberAdapter):
    """OpenAI transcription adapter."""

    accepts_api_key = True

    def __init__(self, config: dict):
        super().__init__(config)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            key = self.credential()
            self._client = OpenAI(api_key=key)
        return self._client

    def _transcribe(
        self, audio, *, model="whisper-1", timestamp_granularities=None, **native_kwargs
    ) -> Transcript:
        from scribed.util import cleanup_temp, ensure_file_path

        client = self._get_client()
        # whisper-1 supports verbose_json (segments, words); gpt-4o models do not.
        verbose = has_capability(self.backend_id, "word_timestamps", model)
        path, is_temp = ensure_file_path(audio, suffix=".wav")
        try:
            with open(path, "rb") as fh:
                create_kwargs = dict(model=model, file=fh, **native_kwargs)
                if verbose:
                    create_kwargs["response_format"] = "verbose_json"
                    if timestamp_granularities:
                        create_kwargs["timestamp_granularities"] = (
                            timestamp_granularities
                        )
                elif timestamp_granularities:
                    warnings.warn(
                        f"{model!r} returns no word timestamps; use model='whisper-1'.",
                        stacklevel=2,
                    )
                resp = client.audio.transcriptions.create(**create_kwargs)
        finally:
            cleanup_temp(path, is_temp)
        return verbose_json_to_transcript(resp, backend_id=self.backend_id)
