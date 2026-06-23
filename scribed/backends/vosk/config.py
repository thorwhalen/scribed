"""Configuration for the Vosk (Kaldi) backend.

Vosk is an offline, streaming speech-recognition toolkit built on Kaldi. It runs
fully locally with no network call and supports incremental (chunked) decoding,
which makes it a good fit for low-latency / privacy-sensitive transcription.

Vosk needs **16 kHz mono 16-bit PCM** audio; the adapter handles resampling and
PCM conversion, so callers can pass any supported audio input.

Model selection:

- ``SCRIBED_VOSK_MODEL`` — if set, a filesystem path to an unpacked Vosk model
  directory (``Model(model_path=...)``). Preferred when present.
- Otherwise the adapter uses ``Model(lang=<language>)`` (default ``"en-us"``),
  which auto-downloads a small model for that language on first use. The
  ``language`` request kwarg picks the lang code.
"""

BACKEND_CONFIG = {
    "id": "vosk",
    "name": "Vosk",
    "display_name": "Vosk (Kaldi)",
    "pip_install": "vosk",
    "import_name": "vosk",
    "license": "Apache-2.0",
    "is_local": True,
    "is_remote": False,
    "capabilities": ["word_timestamps", "stream"],
    "default_for": [],
    "api_env_var": "",
    "description": "Offline streaming speech recognition via Vosk/Kaldi (local, word timestamps).",
    "param_map": {
        # Used to pick the auto-download model lang when no SCRIBED_VOSK_MODEL
        # path is set; consumed in the adapter, not passed to a native engine.
        "language": {"native_name": "language"},
        "diarize": None,  # Vosk does not diarize
        "word_timestamps": None,  # always on (SetWords(True)); not a native kwarg
    },
}
