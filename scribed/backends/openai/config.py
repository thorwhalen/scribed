"""Configuration for the OpenAI transcription backend.

Uses OpenAI's hosted audio-transcriptions endpoint. ``whisper-1`` returns rich
``verbose_json`` (segments + timing); the ``gpt-4o-transcribe`` /
``gpt-4o-mini-transcribe`` models return text/json only (no segment timing).
"""

BACKEND_CONFIG = {
    "id": "openai",
    "name": "OpenAI",
    "display_name": "OpenAI (whisper-1 / gpt-4o-transcribe)",
    "pip_install": "openai",
    "import_name": "openai",
    "license": "proprietary",
    "is_local": False,
    "is_remote": True,
    "capabilities": ["word_timestamps", "translate"],
    "default_for": [],
    "api_env_var": "OPENAI_API_KEY",
    "description": "OpenAI hosted transcription (whisper-1 / gpt-4o-transcribe).",
    "param_map": {
        "language": {"native_name": "language"},
        "model": {"native_name": "model", "default": "whisper-1"},
        "prompt": {"native_name": "prompt"},
        "temperature": {"native_name": "temperature"},
        "diarize": None,  # OpenAI does not diarize
    },
}
