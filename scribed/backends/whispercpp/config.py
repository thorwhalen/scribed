"""Configuration for the whisper.cpp (pywhispercpp) backend.

``pywhispercpp`` is a thin Python binding over ggerganov's whisper.cpp — a pure
C/C++ implementation of Whisper with no Python ML stack. It runs fully locally,
excels on Apple Silicon (Metal) and CPU, and keeps memory low via quantized ggml
models. The ggml weights for a model size are downloaded automatically on first
use.

Model selection is read from the environment so the default just works, while
power users can tune it:

- ``SCRIBED_WHISPERCPP_MODEL`` (default ``"base"``; e.g. ``small``, ``large-v3``,
  or a direct path to a ``ggml-*.bin`` file)

…or pass ``model=`` to a transcribe call. The whisper.cpp engine returns timed
segments (no per-word timestamps by default). A per-segment confidence (the
geometric mean of token probabilities) is available and surfaced when present.
"""

BACKEND_CONFIG = {
    "id": "whispercpp",
    "name": "whisper.cpp",
    "display_name": "whisper.cpp (pywhispercpp)",
    "pip_install": "pywhispercpp",
    "import_name": "pywhispercpp",
    "license": "MIT",
    "is_local": True,
    "is_remote": False,
    "capabilities": ["translate"],
    "default_for": [],
    "api_env_var": "",
    "description": "Local whisper.cpp via pywhispercpp (pure C/C++, great on Apple Silicon).",
    "param_map": {
        "language": {"native_name": "language"},  # None/"" => auto-detect
        "model": {
            "native_name": "model"
        },  # popped in _transcribe (model-construction arg)
        "word_timestamps": None,  # whisper.cpp has no per-word timestamps by default
        "diarize": None,  # not supported (tinydiarize only; out of scope here)
    },
}
