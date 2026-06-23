"""Adapter for the Google Cloud Speech-to-Text (v1) backend.

Maps scribed's normalized request onto ``google.cloud.speech`` and the response
onto a :class:`scribed.base.Transcript`. The audio is decoded to a mono float32
waveform and re-encoded as int16 LINEAR16 PCM at the *source* sample rate (Google
accepts 8000-48000 Hz for LINEAR16, so no resampling is needed), which avoids
format/encoding guesswork. ``long_running_recognize`` is used for robustness with
audio longer than a minute.

The SDK and credentials are resolved lazily so ``import scribed`` stays
dependency-free. Google uses Application Default Credentials
(``GOOGLE_APPLICATION_CREDENTIALS``); the client picks them up from the
environment, so no ``api_key`` is passed.
"""

from __future__ import annotations

from collections import Counter

from scribed.base import Transcript
from scribed.make_backend import BaseTranscriberAdapter, make_segment, make_word

#: Language used when the caller does not specify one (Google requires a code).
DFLT_LANGUAGE_CODE = "en-US"
#: Timeout (seconds) waiting on the long-running recognize operation.
DFLT_OP_TIMEOUT = 600


def _pcm16_bytes(wave):
    """Encode a numpy float32 mono waveform as little-endian int16 PCM bytes."""
    import numpy as np

    return (np.clip(wave, -1.0, 1.0) * 32767).astype("<i2").tobytes()


def _word_speaker(w):
    """Return the diarization speaker tag for a word as a string, or ``None``."""
    tag = getattr(w, "speaker_tag", 0)
    return str(tag) if tag else None


def _majority_speaker(words):
    """Most common (non-None) word-level speaker label, or ``None``."""
    tags = [w.speaker for w in words if w.speaker]
    if not tags:
        return None
    return Counter(tags).most_common(1)[0][0]


class Adapter(BaseTranscriberAdapter):
    """Google Cloud Speech-to-Text (v1) adapter."""

    def _transcribe(
        self,
        audio,
        *,
        language_code=None,
        diarize=False,
        model=None,
        **native_kwargs,
    ) -> Transcript:
        from google.cloud import speech

        from scribed.credentials import resolve_credential
        from scribed.util import to_waveform

        # Optional friendly check: surface a guidance error if nothing is
        # configured. ADC is picked up by the client from the environment, so we
        # do NOT pass an api_key.
        resolve_credential(
            "google-speech",
            env_var=self.config.get("api_env_var") or None,
            required=False,
        )

        # Decode to mono float32 at the SOURCE sample rate, then to int16 PCM.
        wave, sr = to_waveform(audio)
        pcm_bytes = _pcm16_bytes(wave)

        diarization_config = (
            speech.SpeakerDiarizationConfig(enable_speaker_diarization=True)
            if diarize
            else None
        )
        config_kwargs = dict(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=int(sr),
            audio_channel_count=1,
            language_code=language_code or DFLT_LANGUAGE_CODE,
            enable_word_time_offsets=True,
            enable_automatic_punctuation=True,
            diarization_config=diarization_config,
        )
        if model:
            config_kwargs["model"] = model
        config_kwargs.update(native_kwargs)

        config = speech.RecognitionConfig(**config_kwargs)
        audio_msg = speech.RecognitionAudio(content=pcm_bytes)

        client = speech.SpeechClient()
        op = client.long_running_recognize(config=config, audio=audio_msg)
        resp = op.result(timeout=DFLT_OP_TIMEOUT)

        segments = self._segments_from_response(resp, diarize=diarize)
        return Transcript.from_segments(
            segments,
            backend=self.backend_id,
            raw=resp,
            language=language_code or DFLT_LANGUAGE_CODE,
        )

    @staticmethod
    def _segments_from_response(resp, *, diarize) -> list:
        """Build segments from a recognize response (handles Google's quirks).

        One segment per result's top alternative. With diarization, Google tags
        speakers only on the words of the LAST result's top alternative; those
        per-word tags are surfaced on the words and a majority tag is set as the
        segment speaker.
        """
        results = list(getattr(resp, "results", []) or [])
        segments = []
        for result in results:
            alternatives = getattr(result, "alternatives", None) or []
            if not alternatives:
                continue
            alt = alternatives[0]
            raw_words = list(getattr(alt, "words", None) or [])
            words = [
                make_word(
                    w.word,
                    start=w.start_time.total_seconds(),
                    end=w.end_time.total_seconds(),
                    speaker=_word_speaker(w),
                )
                for w in raw_words
            ]
            start = words[0].start if words else None
            end = words[-1].end if words else None
            seg_speaker = _majority_speaker(words) if diarize else None
            segments.append(
                make_segment(
                    alt.transcript,
                    start=start,
                    end=end,
                    confidence=getattr(alt, "confidence", None),
                    speaker=seg_speaker,
                    words=words,
                )
            )
        return segments
