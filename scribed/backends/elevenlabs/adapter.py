"""Adapter for the ElevenLabs Scribe transcription backend.

Maps scribed's normalized request onto ``client.speech_to_text.convert`` (model
``scribe_v1``) and the response onto a :class:`scribed.base.Transcript`.

Scribe's response has no segment structure: it returns the full ``text`` plus a
flat ``words`` stream where each item carries ``text``, ``start``/``end`` (in
seconds), a ``type`` (``"word"`` | ``"spacing"`` | ``"audio_event"``) and — when
``diarize=True`` — a ``speaker_id``. This adapter filters the stream down to
actual words, then groups *consecutive* words by ``speaker_id`` into segments
(starting a new segment whenever the speaker changes). When no speaker ids are
present (e.g. ``diarize=False``), all words form a single segment. The full
``resp.text`` is always carried through as the authoritative transcript.

The client and credential are resolved lazily so ``import scribed`` stays
dependency-free.
"""

from __future__ import annotations

import math

from scribed.base import Transcript
from scribed.make_backend import BaseTranscriberAdapter, make_segment, make_word


def _logprob_to_conf(logprob):
    """Map a per-word log-probability to a rough ``[0, 1]`` confidence."""
    if logprob is None:
        return None
    try:
        return math.exp(float(logprob))  # logprob <= 0 => exp in (0, 1]
    except (TypeError, ValueError, OverflowError):
        return None


def _speaker_str(speaker):
    """Normalize a speaker id to a non-empty ``str`` or ``None``."""
    s = str(speaker) if speaker is not None else ""
    return s or None


class Adapter(BaseTranscriberAdapter):
    """ElevenLabs Scribe transcription adapter (caches one client lazily)."""

    accepts_api_key = True

    def __init__(self, config: dict):
        super().__init__(config)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from elevenlabs.client import ElevenLabs

            key = self.credential()
            self._client = ElevenLabs(api_key=key)
        return self._client

    def _convert(
        self,
        *,
        model_id="scribe_v1",
        diarize=False,
        **source_and_native,
    ) -> Transcript:
        """One ``speech_to_text.convert`` call; the source is ``file=`` or ``cloud_storage_url=``."""
        resp = self._get_client().speech_to_text.convert(
            model_id=model_id,
            diarize=diarize,
            timestamps_granularity="word",  # the words build the segments
            **source_and_native,
        )

        text = getattr(resp, "text", None) or ""
        language = getattr(resp, "language_code", None)
        duration = getattr(resp, "audio_duration_secs", None)

        try:
            segments = _segments_from_words(getattr(resp, "words", None) or [])
        except Exception:  # noqa: BLE001 - any parsing hiccup falls back to text
            segments = None

        if segments:
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

    def _transcribe(self, audio, **native_kwargs) -> Transcript:
        from scribed.util import load_audio_bytes

        return self._convert(file=load_audio_bytes(audio), **native_kwargs)

    def can_fetch_url(self, url: str) -> bool:
        """Scribe fetches only HTTPS addresses (``cloud_storage_url``)."""
        return super().can_fetch_url(url) and url.lower().startswith("https://")

    def _transcribe_url(self, url: str, **native_kwargs) -> Transcript:
        """Scribe fetches ``url`` itself (up to 2 GB; pre-signed URLs work).

        Direct file addresses only: page URLs (YouTube, ...) are the SDK's ``source_url``.
        """
        return self._convert(cloud_storage_url=url, **native_kwargs)


def _segments_from_words(raw_words):
    """Group consecutive Scribe words by ``speaker_id`` into segments.

    Skips ``spacing``/``audio_event`` items, building a normalized
    :class:`~scribed.base.Word` per actual word and starting a new segment
    whenever ``speaker_id`` changes. If no speaker ids are present, all words
    end up in a single segment.
    """
    segments = []
    cur_words = []
    cur_speaker = None  # sentinel-free: track via a flag
    have_group = False

    def flush():
        if not cur_words:
            return
        starts = [w.start for w in cur_words if w.start is not None]
        ends = [w.end for w in cur_words if w.end is not None]
        segments.append(
            make_segment(
                " ".join(w.text for w in cur_words).strip(),
                start=min(starts) if starts else None,
                end=max(ends) if ends else None,
                speaker=cur_speaker,
                words=list(cur_words),
            )
        )

    for w in raw_words:
        if getattr(w, "type", "word") != "word":
            continue  # skip "spacing" / "audio_event"
        speaker = _speaker_str(getattr(w, "speaker_id", None))
        word = make_word(
            getattr(w, "text", "") or "",
            start=getattr(w, "start", None),
            end=getattr(w, "end", None),
            confidence=_logprob_to_conf(getattr(w, "logprob", None)),
            speaker=speaker,
        )
        if have_group and speaker != cur_speaker:
            flush()
            cur_words = []
        cur_speaker = speaker
        cur_words.append(word)
        have_group = True

    flush()
    return segments
