"""Configuration for the Groq (hosted Whisper) transcription backend.

Groq serves OpenAI's Whisper models (``whisper-large-v3`` and the faster
``whisper-large-v3-turbo``) on its LPU inference stack — extremely fast and
cheap. The HTTP API mirrors OpenAI's audio-transcriptions endpoint, so
``response_format="verbose_json"`` yields the same segment shape (``start``,
``end``, ``text``, ``avg_logprob``, ``no_speech_prob``) and word/segment
timestamp granularities. ``turbo`` is the default for its speed/cost; switch to
``whisper-large-v3`` for maximum accuracy.
"""

BACKEND_CONFIG = {
    "id": "groq",
    "name": "Groq",
    "display_name": "Groq (Whisper large-v3 / turbo)",
    "pip_install": "groq",
    "import_name": "groq",
    "license": "proprietary",
    "is_local": False,
    "is_remote": True,
    "capabilities": ["word_timestamps", "translate"],
    "default_for": [],
    "api_env_var": "GROQ_API_KEY",
    "description": (
        "Groq hosted Whisper transcription (whisper-large-v3 / turbo) — "
        "fast, cheap, OpenAI-compatible verbose_json segments."
    ),
    "param_map": {
        "language": {"native_name": "language"},
        "model": {"native_name": "model", "default": "whisper-large-v3-turbo"},
        "prompt": {"native_name": "prompt"},
        "temperature": {"native_name": "temperature"},
        "diarize": None,  # Groq's Whisper endpoint does not diarize
    },
}
