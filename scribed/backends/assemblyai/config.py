"""Configuration for the AssemblyAI (Universal) transcription backend.

AssemblyAI is a hosted speech-to-text API built on its Universal model. It
provides speaker diarization (``speaker_labels``), word-level timestamps, and a
suite of audio-intelligence features (sentiment, topics, summarization, ...).
The SDK uploads local files for you, so a transcribe call accepts either a local
file path or a publicly reachable URL.

The two normalized params scribed exposes here map onto
``assemblyai.TranscriptionConfig`` fields: ``language`` -> ``language_code`` and
``diarize`` -> ``speaker_labels``. Additional native config (sentiment_analysis,
iab_categories, summarization, ...) can be passed through and is forwarded to
``TranscriptionConfig`` verbatim.
"""

BACKEND_CONFIG = {
    "id": "assemblyai",
    "name": "AssemblyAI",
    "display_name": "AssemblyAI (Universal)",
    "pip_install": "assemblyai",
    "import_name": "assemblyai",
    "license": "proprietary",
    "is_local": False,
    "is_remote": True,
    "capabilities": ["diarize", "word_timestamps"],
    "default_for": [],
    "api_env_var": "ASSEMBLYAI_API_KEY",
    "description": (
        "AssemblyAI hosted transcription (Universal model) with speaker "
        "diarization, word timestamps, and audio intelligence."
    ),
    "param_map": {
        # Feed native kwargs to assemblyai.TranscriptionConfig(**native_kwargs).
        "language": {"native_name": "language_code"},  # None => auto-detect
        "diarize": {"native_name": "speaker_labels"},  # bool
    },
}
