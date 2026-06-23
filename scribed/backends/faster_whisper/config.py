"""Configuration for the faster-whisper backend.

faster-whisper runs OpenAI's Whisper models via CTranslate2 — fast, accurate, and
CPU-capable, with no system ffmpeg required (it decodes via bundled PyAV). This is
scribed's default local engine.

Model selection (and device / compute type) are read from the environment so the
default just works, while power users can tune them:

- ``SCRIBED_FASTER_WHISPER_MODEL`` (default ``"base"``; e.g. ``small``, ``large-v3``)
- ``SCRIBED_FASTER_WHISPER_DEVICE`` (default ``"auto"``; ``cpu`` / ``cuda``)
- ``SCRIBED_FASTER_WHISPER_COMPUTE`` (default ``"default"``; e.g. ``int8``, ``float16``)

…or pass ``model=`` to a transcribe call.
"""

BACKEND_CONFIG = {
    "id": "faster-whisper",
    "name": "faster-whisper",
    "display_name": "faster-whisper (CTranslate2)",
    "pip_install": "faster-whisper",
    "import_name": "faster_whisper",
    "license": "MIT",
    "is_local": True,
    "is_remote": False,
    "capabilities": ["word_timestamps", "translate"],
    "default_for": ["transcribe"],
    "api_env_var": "",
    "description": "Fast local Whisper via CTranslate2 (scribed's default local engine).",
    "param_map": {
        "language": {"native_name": "language"},  # None => auto-detect
        "word_timestamps": {"native_name": "word_timestamps", "default": False},
        "task": {"native_name": "task"},  # "transcribe" | "translate"
        "beam_size": {"native_name": "beam_size"},
        "vad_filter": {"native_name": "vad_filter"},
        "initial_prompt": {"native_name": "initial_prompt"},
        "model": {
            "native_name": "model"
        },  # popped in _transcribe (model-construction arg)
        "diarize": None,  # not supported (use whisperx for local diarization)
    },
}
