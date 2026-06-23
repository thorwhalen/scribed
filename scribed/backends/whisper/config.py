"""Configuration for the OpenAI Whisper (PyTorch) backend.

This is the original PyTorch reference implementation of Whisper
(``openai-whisper``), run fully locally. Unlike faster-whisper it requires a
system ``ffmpeg`` to decode audio, so the adapter always hands the engine a real
file path.

Model selection is read from the environment so the default just works, while
power users can tune it:

- ``SCRIBED_WHISPER_MODEL`` (default ``"base"``; e.g. ``small``, ``large-v3``)

…or pass ``model=`` to a transcribe call. Word-level timestamps are available
(``word_timestamps=True``) and translation via ``task="translate"``.
"""

BACKEND_CONFIG = {
    "id": "whisper",
    "name": "openai-whisper",
    "display_name": "OpenAI Whisper (PyTorch)",
    "pip_install": "openai-whisper",
    "import_name": "whisper",
    "license": "MIT",
    "is_local": True,
    "is_remote": False,
    "capabilities": ["word_timestamps", "translate"],
    "default_for": [],
    "api_env_var": "",
    "description": "Original PyTorch reference Whisper, run locally (needs system ffmpeg).",
    "param_map": {
        "language": {"native_name": "language"},  # None => auto-detect
        "word_timestamps": {"native_name": "word_timestamps", "default": False},
        "task": {"native_name": "task"},  # "transcribe" | "translate"
        "initial_prompt": {"native_name": "initial_prompt"},
        "model": {"native_name": "model"},  # popped in _transcribe (model-load arg)
        "diarize": None,  # not supported by reference Whisper
    },
}
