"""scribed — one facade over many speech-to-text engines, plus a ledger to choose.

Transcription ("turn this audio into text") is solved a dozen different ways:
local engines (Whisper, faster-whisper, whisper.cpp, Vosk), fast cheap cloud APIs
(Groq, OpenAI), and feature-rich premium services (Deepgram, AssemblyAI, Google,
ElevenLabs) — each with its own install, API, pricing, latency, language coverage,
diarization support, and quirks. scribed gives you:

1. **A uniform facade.** Call :func:`transcribe` and get the same
   :class:`~scribed.base.Transcript` back no matter which backend ran::

       import scribed
       t = scribed.transcribe("talk.mp3")          # default (first installed) backend
       print(t)                                     # -> the transcript text
       t = scribed.transcribe("talk.mp3", backend="deepgram", diarize=True)
       print(t.srt)                                 # -> SRT subtitles
       for seg in t:
           print(seg.start, seg.speaker, seg.text)

   Convenience: :func:`transcribe_text` returns just the string.

2. **A ledger / gallery** of *every* engine we researched — not only the ones
   with a working facade — so you can choose with eyes open::

       scribed.catalog                                  # the whole ledger
       scribed.find(is_local=True, open_source=True)    # filter it
       scribed.find(diarization="yes", is_remote=True)
       scribed.catalog.to_dataframe()                   # browse as a table

   The ledger lives in data (``scribed/data/backends.json``), not code.

3. **Tools to build new facades.** The catalog is large; scribed ships a facade
   for a curated subset and gives you the machinery (and a SKILL) to add any
   other one in minutes::

       from scribed.make_backend import scaffold_backend, validate_adapter
       scaffold_backend("speechmatics")   # generate a backend package from the ledger
       validate_adapter("faster-whisper") # smoke-test an adapter end to end

Three tiers of access, from simplest to most powerful::

    scribed.transcribe(audio)                              # facade, default backend
    scribed.services.deepgram.transcribe(audio, diarize=True)  # pick a backend
    scribed.services.deepgram.adapter                      # raw engine adapter
"""

from scribed.base import (
    AudioInput,
    Channel,
    Segment,
    TimeSpan,
    Transcript,
    Word,
)
from scribed.catalog import BackendInfo, Catalog, catalog
from scribed.registry import (
    get_config,
    get_default_backend,
    list_backends,
    register_backend,
)
from scribed.services import ServiceCollection
from scribed.make_backend import (
    BaseTranscriberAdapter,
    make_segment,
    make_word,
    scaffold_backend,
    validate_adapter,
)
from scribed.install import (
    Requirements,
    available_backends,
    check,
    doctor,
    install,
    requirements,
)
from scribed.status import (
    backend_ids,
    backend_info,
    is_set_up,
    is_tested,
    names_with_sites,
    status_table,
)

__all__ = [
    "transcribe",
    "transcribe_text",
    "services",
    "catalog",
    "find",
    "list_backends",
    "register_backend",
    "get_default_backend",
    "get_config",
    "Transcript",
    "Segment",
    "Word",
    "TimeSpan",
    "Channel",
    "AudioInput",
    # streaming surface (lazily imported; see module __getattr__)
    "transcribe_live",
    "iter_live",
    "Transcriber",
    "AudioSource",
    "file_to_stream",
    "from_mic",
    "VAD",
    "EnergyVAD",
    "SileroVAD",
    "segment_utterances",
    "BackendInfo",
    "Catalog",
    "ServiceCollection",
    "BaseTranscriberAdapter",
    "make_segment",
    "make_word",
    "scaffold_backend",
    "validate_adapter",
    "requirements",
    "check",
    "doctor",
    "install",
    "available_backends",
    "Requirements",
    "backend_ids",
    "backend_info",
    "status_table",
    "names_with_sites",
    "is_set_up",
    "is_tested",
    "__version__",
]

# Derive the version from installed package metadata (the pyproject SSOT, which CI
# auto-bumps) so __version__ never drifts from a hardcoded literal.
from importlib.metadata import PackageNotFoundError as _PNFE, version as _version

try:
    __version__ = _version("scribed")
except _PNFE:  # running from a source tree without install metadata
    __version__ = "0.0.0+source"
del _version, _PNFE

#: Singleton service collection for per-backend access (``services.deepgram``).
services = ServiceCollection()


def transcribe(audio: AudioInput, *, backend: str = None, **kwargs) -> Transcript:
    """Transcribe audio with any backend, returning a normalized result.

    Args:
        audio: A path, ``http(s)`` URL, ``bytes``, file-like object, or numpy
            waveform.
        backend: Backend id (see :func:`list_backends`). Defaults to the first
            *installed* implemented backend (see :func:`get_default_backend`).
        **kwargs: Normalized, backend-translated options (e.g. ``language``,
            ``diarize``, ``word_timestamps``). Unknown options for the chosen
            backend are warned about and dropped.

    Returns:
        A :class:`~scribed.base.Transcript` (``str(t)`` is the text; ``t.srt`` /
        ``t.vtt`` give subtitles; iterate it for segments).
    """
    backend = backend or get_default_backend()
    return services[backend].transcribe(audio, **kwargs)


def transcribe_text(audio: AudioInput, *, backend: str = None, **kwargs) -> str:
    """Like :func:`transcribe` but returns just the transcript text string."""
    return transcribe(audio, backend=backend, **kwargs).text


def find(**criteria) -> Catalog:
    """Filter the ledger; shorthand for :meth:`scribed.catalog.Catalog.filter`.

    Example::

        scribed.find(is_local=True, open_source=True, diarization="yes")
        scribed.find(implemented=True)        # only backends scribed can run now
    """
    return catalog.filter(**criteria)


# ---------------------------------------------------------------------------
# Lazy streaming surface (PEP 562)
# ---------------------------------------------------------------------------
# The real-time API lives in scribed.streaming / scribed.vad, which need numpy.
# Importing them lazily on first attribute access keeps ``import scribed`` light
# (no numpy, no audio libs) for the batch-only and ledger-only use cases.

_LAZY_ATTRS = {
    "transcribe_live": "scribed.streaming",
    "iter_live": "scribed.streaming",
    "Transcriber": "scribed.streaming",
    "AudioSource": "scribed.streaming",
    "file_to_stream": "scribed.streaming",
    "from_mic": "scribed.streaming",
    "VAD": "scribed.vad",
    "EnergyVAD": "scribed.vad",
    "SileroVAD": "scribed.vad",
    "segment_utterances": "scribed.vad",
}


def __getattr__(name: str):
    """Lazily resolve the streaming symbols (PEP 562 module-level hook)."""
    module_path = _LAZY_ATTRS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    return getattr(importlib.import_module(module_path), name)


def __dir__():
    return sorted([*globals().keys(), *_LAZY_ATTRS])
