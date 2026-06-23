"""Adapter for the Vosk (Kaldi) backend.

Vosk is an offline Kaldi-based recognizer that decodes **16 kHz mono 16-bit PCM**
fed in chunks. This adapter reads any supported audio input as a float32 mono
waveform, resamples to 16 kHz when needed, converts to little-endian int16 PCM,
streams it through a :class:`vosk.KaldiRecognizer`, and maps Vosk's per-result
JSON (with ``SetWords(True)`` word timings/confidences) onto a
:class:`scribed.base.Transcript`.

The engine SDK is imported lazily and the model is cached on the adapter so
``import scribed`` stays dependency-free and repeated calls reuse the model.

Model selection:

- ``SCRIBED_VOSK_MODEL`` (a path to an unpacked model dir) is preferred when set.
- Otherwise ``Model(lang=<language>)`` (default ``"en-us"``) auto-downloads a
  small model for the requested language on first use.
"""

from __future__ import annotations

import json
import os

from scribed.base import Transcript
from scribed.make_backend import BaseTranscriberAdapter, make_segment, make_word

#: Sample rate Vosk requires (Hz).
_VOSK_SAMPLE_RATE = 16_000
#: How many waveform samples to feed the recognizer per AcceptWaveform call.
_CHUNK_SAMPLES = 4_000


def _resample(wave, sr_in: int, sr_out: int):
    """Linear-resample a 1-D float waveform from ``sr_in`` to ``sr_out`` Hz.

    Uses ``numpy.interp`` over a new uniform time base. A no-op when the rates
    already match. Good enough for ASR-grade 16 kHz conditioning (Vosk is robust
    to the mild aliasing a linear interpolator introduces).
    """
    if sr_in == sr_out:
        return wave

    import numpy as np

    n_in = len(wave)
    if n_in == 0:
        return wave
    duration = n_in / float(sr_in)
    n_out = int(round(duration * sr_out))
    if n_out <= 0:
        return wave[:0]
    # Sample positions (in seconds) of the source and target grids.
    t_in = np.arange(n_in, dtype=np.float64) / float(sr_in)
    t_out = np.arange(n_out, dtype=np.float64) / float(sr_out)
    return np.interp(t_out, t_in, wave).astype(np.float32)


def _to_pcm16_bytes(wave):
    """Convert a float32 waveform in ``[-1, 1]`` to little-endian int16 PCM bytes."""
    import numpy as np

    clipped = np.clip(wave, -1.0, 1.0)
    return (clipped * 32767.0).astype("<i2").tobytes()


def _segment_from_result(result: dict):
    """Build a :class:`Segment` from one Vosk result JSON, or ``None`` if empty.

    Derives the segment time span from the first/last word when word timings are
    present; carries word-level units with their per-word confidences.
    """
    text = (result.get("text") or "").strip()
    if not text:
        return None
    word_records = result.get("result") or []
    words = [
        make_word(
            w["word"],
            start=w.get("start"),
            end=w.get("end"),
            confidence=w.get("conf"),  # already ~[0, 1]
        )
        for w in word_records
    ]
    if word_records:
        start = word_records[0].get("start")
        end = word_records[-1].get("end")
    else:
        start = end = None
    return make_segment(text, start=start, end=end, words=words)


class Adapter(BaseTranscriberAdapter):
    """Vosk adapter (caches one model per requested language / model path)."""

    def __init__(self, config: dict):
        super().__init__(config)
        # path -> Model. Keyed by the resolved model identity (path or lang) so a
        # process that transcribes several languages reuses each model.
        self._models: dict = {}

    def _get_model(self, language=None):
        from vosk import Model, SetLogLevel

        SetLogLevel(-1)  # silence Kaldi's verbose stderr logging

        model_path = os.environ.get("SCRIBED_VOSK_MODEL")
        if model_path:
            key = ("path", model_path)
        else:
            key = ("lang", language or "en-us")

        if key not in self._models:
            if model_path:
                self._models[key] = Model(model_path=model_path)
            else:
                self._models[key] = Model(lang=key[1])
        return self._models[key]

    def _transcribe(self, audio, *, language=None, **native_kwargs) -> Transcript:
        from vosk import KaldiRecognizer

        from scribed.util import to_waveform

        # to_waveform does NOT resample, so condition to 16 kHz ourselves.
        wave, sr = to_waveform(audio, sample_rate=_VOSK_SAMPLE_RATE)
        if getattr(wave, "ndim", 1) > 1:  # defensive: ensure mono
            import numpy as np

            wave = wave.mean(axis=1).astype(np.float32)
        wave = _resample(wave, sr, _VOSK_SAMPLE_RATE)
        pcm = _to_pcm16_bytes(wave)

        model = self._get_model(language)
        rec = KaldiRecognizer(model, _VOSK_SAMPLE_RATE)
        rec.SetWords(True)

        all_results = []
        bytes_per_sample = 2  # int16
        step = _CHUNK_SAMPLES * bytes_per_sample
        for offset in range(0, len(pcm), step):
            chunk = pcm[offset : offset + step]
            if not chunk:
                break
            if rec.AcceptWaveform(chunk):
                all_results.append(json.loads(rec.Result()))
        all_results.append(json.loads(rec.FinalResult()))

        segments = []
        for result in all_results:
            seg = _segment_from_result(result)
            if seg is not None:
                segments.append(seg)

        return Transcript.from_segments(
            segments, backend=self.backend_id, raw=all_results
        )
