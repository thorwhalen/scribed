"""Generic audio conditioning helpers (decode, down-mix, resample).

scribed's batch facade accepts files/URLs/bytes and decodes them lazily where the
engine needs a path. The *streaming* surface (:mod:`scribed.streaming`) works in
terms of in-memory ``float32`` mono waveforms instead, so these helpers turn
arbitrary audio into the shape an STT model wants — **mono, float32, 16 kHz** — and
back into WAV ``bytes`` when a batch engine is fed a streamed utterance.

Everything here is *channel-agnostic*: multi-source/channel concerns (mic vs system
"me vs them") belong to the consumer, not to generic transcription. These functions
need numpy (and ``load_audio`` needs ``soundfile``); they are imported lazily by the
streaming layer so plain ``import scribed`` never pulls numpy in. Install the deps
with ``pip install 'scribed[audio]'``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple, Union

import numpy as np

#: STT engines expect 16 kHz mono float32; this is the canonical target rate.
STT_SAMPLE_RATE: int = 16_000


def load_audio(
    path: Union[str, Path], *, always_2d: bool = True
) -> Tuple[np.ndarray, int]:
    """Load an audio file as float32 samples plus its native sample rate.

    Args:
        path: Path to any libsndfile-readable file (wav, flac, aiff, ogg, ...).
            Compressed formats (mp3/m4a/webm/opus) fall back to ``ffmpeg``.
        always_2d: If True, always return shape ``(n_samples, n_channels)``.

    Returns:
        ``(data, sample_rate)`` where ``data`` is float32 in roughly ``[-1, 1]``.
    """
    try:
        import soundfile as sf
    except ImportError as e:  # pragma: no cover - guidance path
        raise ImportError(
            "Reading audio needs `soundfile`. Install with: "
            "pip install 'scribed[audio]'\n(it bundles libsndfile)."
        ) from e
    try:
        data, sr = sf.read(str(path), dtype="float32", always_2d=always_2d)
        return data, int(sr)
    except Exception:
        # libsndfile can't read it (e.g. mp3/m4a/webm/opus from a browser
        # recording). Fall back to ffmpeg, which decodes virtually anything.
        import os

        wav = _ffmpeg_decode_to_wav(path)
        try:
            data, sr = sf.read(wav, dtype="float32", always_2d=always_2d)
            return data, int(sr)
        finally:
            try:
                os.unlink(wav)
            except OSError:
                pass


def _ffmpeg_decode_to_wav(path: Union[str, Path]) -> str:
    """Decode any audio file to a temp 16-bit PCM WAV via ffmpeg (channels kept)."""
    import shutil
    import subprocess
    import tempfile
    import os

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            f"Could not read {path} with libsndfile, and ffmpeg is not on PATH to "
            "convert it. Install ffmpeg (e.g. `brew install ffmpeg`) to handle "
            "mp3/m4a/webm/opus (incl. browser recordings)."
        )
    fd, out = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    subprocess.run(
        [ffmpeg, "-y", "-i", str(path), "-c:a", "pcm_s16le", out],
        check=True,
        capture_output=True,
    )
    return out


def to_mono(data: np.ndarray) -> np.ndarray:
    """Down-mix to mono by averaging channels. 1-D input is returned as-is."""
    data = np.asarray(data)
    if data.ndim == 2:
        return data.mean(axis=1).astype("float32", copy=False)
    return data.astype("float32", copy=False)


def resample(mono: np.ndarray, sr: int, target: int = STT_SAMPLE_RATE) -> np.ndarray:
    """Resample a mono float array to ``target`` Hz.

    Prefers `soxr` (fast, high quality); falls back to linear interpolation so the
    package still works without it (good enough for small STT models).
    """
    mono = np.asarray(mono, dtype="float32")
    if sr == target:
        return mono
    try:
        import soxr

        return soxr.resample(mono, sr, target).astype("float32", copy=False)
    except ImportError:
        n_out = int(round(len(mono) * target / sr))
        if n_out <= 0:
            return np.zeros(0, dtype="float32")
        x_old = np.arange(len(mono))
        x_new = np.linspace(0, len(mono), n_out, endpoint=False)
        return np.interp(x_new, x_old, mono).astype("float32")


def to_mono_16k(
    data: np.ndarray, sr: int, *, target: int = STT_SAMPLE_RATE
) -> np.ndarray:
    """Convenience: down-mix to mono and resample to the STT target rate."""
    return resample(to_mono(data), sr, target)


def rms_energy(samples: np.ndarray) -> float:
    """Root-mean-square energy of a sample buffer (``0.0`` for empty)."""
    samples = np.asarray(samples)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples, dtype="float64"))))


def to_wav_bytes(mono: np.ndarray, sample_rate: int) -> bytes:
    """Encode a mono float32 waveform as in-memory WAV ``bytes``.

    Used by the streaming layer to hand a VAD-segmented utterance to a batch
    engine via scribed's ``bytes`` input path — no temp file, no engine change.
    """
    try:
        import soundfile as sf
    except ImportError as e:  # pragma: no cover - guidance path
        raise ImportError(
            "Encoding audio needs `soundfile`. Install with: "
            "pip install 'scribed[audio]'"
        ) from e
    import io

    buf = io.BytesIO()
    sf.write(buf, np.asarray(mono, dtype="float32"), int(sample_rate), format="WAV")
    return buf.getvalue()
