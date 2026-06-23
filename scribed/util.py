"""Audio-input normalization and small shared helpers.

Different ASR backends want their input in different forms: a filesystem path
(local Whisper, faster-whisper — they shell out to ffmpeg), raw ``bytes`` or a
file object (most cloud REST APIs), or a numpy waveform (deep-learning engines).
Callers, meanwhile, want to pass whatever they have — a path, an ``http(s)`` URL,
bytes, a file-like object, or a numpy array. This module bridges the two with a
handful of converters that **lazily** import soundfile / numpy / urllib only when
actually exercised, so ``import scribed`` stays dependency-free.

The key converters:

- :func:`load_audio_bytes` — anything -> encoded audio ``bytes`` (for REST APIs).
- :func:`ensure_file_path` — anything -> a path on disk (writing a temp file for
  in-memory inputs); pair with :func:`cleanup_temp` or use :func:`audio_path`.
- :func:`audio_path` — a context manager yielding a path and cleaning up.
- :func:`to_waveform` — anything -> ``(numpy float32 mono, sample_rate)``.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path
from typing import Iterator, Tuple

from scribed.base import AudioInput

__all__ = [
    "classify_input",
    "is_url",
    "load_audio_bytes",
    "ensure_file_path",
    "cleanup_temp",
    "audio_path",
    "to_waveform",
    "check_import",
]

#: Default sample rate (Hz) used when encoding/decoding raw waveforms. 16 kHz is
#: the de-facto standard for speech models (Whisper, wav2vec2, ...).
DFLT_SAMPLE_RATE = 16_000


def check_import(module_name: str, *, install_hint: str, feature: str = "this"):
    """Import ``module_name`` or raise a friendly, actionable ImportError.

    Centralizes the "you need to ``pip install X``" guidance so adapters and
    converters don't each hand-roll it.
    """
    try:
        import importlib

        return importlib.import_module(module_name)
    except ImportError as e:  # pragma: no cover - exercised via adapters
        raise ImportError(
            f"{feature} requires {module_name!r}. Install it with: "
            f"pip install {install_hint}\nOriginal error: {e}"
        ) from e


def is_url(x: object) -> bool:
    """True if ``x`` is a string that looks like an http(s) URL."""
    return isinstance(x, str) and x.lower().startswith(("http://", "https://"))


def classify_input(audio: AudioInput) -> str:
    """Classify an audio input as ``url``/``path``/``bytes``/``file``/``numpy``.

    Decided structurally (and via duck typing for file objects / numpy) so we
    never import soundfile or numpy just to look at the input.
    """
    if isinstance(audio, (bytes, bytearray)):
        return "bytes"
    if is_url(audio):
        return "url"
    if isinstance(audio, (str, Path)):
        return "path"
    # Duck-type without importing the libs.
    if audio.__class__.__module__.startswith("numpy") or hasattr(audio, "__array__"):
        return "numpy"
    if hasattr(audio, "read"):
        return "file"
    raise TypeError(
        f"Unsupported audio input of type {type(audio).__name__}. Expected a path, "
        "URL, bytes, file-like object, or numpy waveform."
    )


def _fetch_url(url: str, *, timeout: float = 60.0) -> bytes:
    from urllib.request import urlopen  # stdlib, no extra dependency

    with urlopen(url, timeout=timeout) as resp:  # noqa: S310 - user-supplied URL
        return resp.read()


def _encode_wav(waveform, sample_rate: int) -> bytes:
    """Encode a numpy waveform to WAV ``bytes`` via soundfile (lazy import)."""
    sf = check_import(
        "soundfile", install_hint="soundfile", feature="waveform encoding"
    )
    import io

    buf = io.BytesIO()
    sf.write(buf, waveform, sample_rate, format="WAV")
    return buf.getvalue()


def load_audio_bytes(
    audio: AudioInput, *, sample_rate: int = DFLT_SAMPLE_RATE
) -> bytes:
    """Return encoded audio ``bytes`` for any supported input.

    Pass-through for ``bytes``; reads files and file objects; fetches URLs;
    encodes numpy waveforms as WAV (at ``sample_rate``).
    """
    kind = classify_input(audio)
    if kind == "bytes":
        return bytes(audio)
    if kind == "path":
        return Path(os.fspath(audio)).read_bytes()
    if kind == "url":
        return _fetch_url(audio)
    if kind == "file":
        data = audio.read()
        return data if isinstance(data, bytes) else bytes(data)
    # numpy -> encode in-memory
    return _encode_wav(audio, sample_rate)


def ensure_file_path(
    audio: AudioInput, *, suffix: str = ".wav", sample_rate: int = DFLT_SAMPLE_RATE
) -> Tuple[str, bool]:
    """Return ``(path, is_temp)`` for any supported input.

    Existing on-disk paths are returned untouched (``is_temp=False``). In-memory
    inputs (bytes/URL/file/numpy) are written to a temp file (``is_temp=True``);
    the caller is responsible for cleanup (use :func:`cleanup_temp`, or prefer
    the :func:`audio_path` context manager).
    """
    if classify_input(audio) == "path":
        return os.fspath(audio), False
    data = load_audio_bytes(audio, sample_rate=sample_rate)
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="scribed_")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path, True


def cleanup_temp(path: str, is_temp: bool) -> None:
    """Delete ``path`` iff ``is_temp`` (the flag returned by :func:`ensure_file_path`)."""
    if is_temp:
        with contextlib.suppress(OSError):
            os.remove(path)


@contextlib.contextmanager
def audio_path(audio: AudioInput, *, suffix: str = ".wav") -> Iterator[str]:
    """Context manager yielding a filesystem path for ``audio``, cleaning up temps.

    Example::

        with audio_path(raw_bytes) as p:
            segments = model.transcribe(p)
    """
    path, is_temp = ensure_file_path(audio, suffix=suffix)
    try:
        yield path
    finally:
        cleanup_temp(path, is_temp)


def to_waveform(audio: AudioInput, *, sample_rate: int = DFLT_SAMPLE_RATE):
    """Convert any supported input into ``(numpy float32 mono, sample_rate)``.

    Numpy input is returned as-is (paired with ``sample_rate``). Everything else
    is decoded with soundfile and resampled is *not* performed — the returned
    sample rate is whatever the source had (numpy inputs excepted).
    """
    np = check_import("numpy", install_hint="numpy", feature="waveform conversion")
    if classify_input(audio) == "numpy":
        return audio, sample_rate
    sf = check_import("soundfile", install_hint="soundfile", feature="audio decoding")
    with audio_path(audio) as p:
        data, sr = sf.read(p, dtype="float32")
    if getattr(data, "ndim", 1) > 1:  # downmix to mono
        data = data.mean(axis=1).astype(np.float32)
    return data, sr
