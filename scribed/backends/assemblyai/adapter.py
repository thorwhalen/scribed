"""Adapter for the AssemblyAI (Universal) transcription backend.

Maps scribed's normalized request onto ``assemblyai.Transcriber.transcribe`` and
the returned transcript onto a :class:`scribed.base.Transcript`. When speaker
labels are requested AssemblyAI returns ``utterances`` (one diarized speaker
turn each, with nested words); otherwise we build a single segment from the full
text and its word stream. AssemblyAI reports times in **milliseconds**, so we
divide by 1000 to get scribed's seconds. The SDK and credential are resolved
lazily so ``import scribed`` stays dependency-free.
"""

from __future__ import annotations

from scribed.base import Transcript
from scribed.make_backend import BaseTranscriberAdapter, make_segment, make_word


def _ms_to_s(value):
    """Convert an AssemblyAI millisecond time to seconds (``None`` passes through)."""
    return None if value is None else float(value) / 1000.0


def _speaker_str(speaker):
    """Normalize a speaker label to a non-empty ``str`` or ``None``."""
    s = str(speaker) if speaker is not None else ""
    return s or None


class Adapter(BaseTranscriberAdapter):
    """AssemblyAI (Universal) transcription adapter."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._configured = False

    def _ensure_configured(self):
        """Set the SDK's global API key once (lazy import + lazy credential)."""
        if not self._configured:
            import assemblyai as aai

            from scribed.credentials import resolve_credential

            key = resolve_credential(
                "assemblyai",
                env_var=self.config.get("api_env_var") or None,
                required=True,
            )
            aai.settings.api_key = key
            self._configured = True

    def _transcribe(self, audio, **native_kwargs) -> Transcript:
        import assemblyai as aai

        from scribed.util import cleanup_temp, ensure_file_path

        self._ensure_configured()

        config = aai.TranscriptionConfig(**native_kwargs)
        transcriber = aai.Transcriber()

        # The SDK accepts a local path (it uploads) or a URL; give it a path.
        path, is_temp = ensure_file_path(audio)
        try:
            t = transcriber.transcribe(path, config=config)
        finally:
            cleanup_temp(path, is_temp)

        # Surface a failed transcription as an exception (validate_adapter catches it).
        status = getattr(t, "status", None)
        error = getattr(t, "error", None)
        if error or (status is not None and str(status).lower().endswith("error")):
            raise RuntimeError(f"AssemblyAI transcription failed: {error or status}")

        language = getattr(t, "language_code", None)
        utterances = getattr(t, "utterances", None)

        if utterances:
            segments = [
                make_segment(
                    u.text or "",
                    start=_ms_to_s(u.start),
                    end=_ms_to_s(u.end),
                    confidence=u.confidence,
                    speaker=_speaker_str(u.speaker),
                    words=[
                        make_word(
                            w.text,
                            start=_ms_to_s(w.start),
                            end=_ms_to_s(w.end),
                            confidence=w.confidence,
                            speaker=_speaker_str(getattr(w, "speaker", None)),
                        )
                        for w in (getattr(u, "words", None) or [])
                    ],
                )
                for u in utterances
            ]
        else:
            words = [
                make_word(
                    w.text,
                    start=_ms_to_s(w.start),
                    end=_ms_to_s(w.end),
                    confidence=w.confidence,
                    speaker=_speaker_str(getattr(w, "speaker", None)),
                )
                for w in (getattr(t, "words", None) or [])
            ]
            segments = [make_segment(t.text or "", words=words)]

        return Transcript.from_segments(
            segments,
            backend=self.backend_id,
            raw=t,
            text=getattr(t, "text", None),
            language=language,
        )
