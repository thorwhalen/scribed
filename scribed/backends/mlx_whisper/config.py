"""Configuration for the mlx-whisper backend (Whisper on Apple Silicon via MLX).

`mlx-whisper <https://pypi.org/project/mlx-whisper/>`_ is Apple's (ml-explore)
port of OpenAI Whisper to MLX: it runs on the M-series GPU with unified memory, and
returns openai-whisper-shaped results (segments, optional word timestamps).
macOS on Apple Silicon only.

``model`` is either a Hugging Face repo id (``"mlx-community/whisper-large-v3-turbo"``,
the default) or a bare Whisper size (``"tiny"``, ``"base"``, ``"small"``,
``"medium"``, ``"large-v3"``, ``"turbo"``), resolved by
:func:`scribed.backends.mlx_whisper.adapter.resolve_model_repo`.
"""

#: Default MLX Whisper weights (fast and accurate on M2+).
DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"

BACKEND_CONFIG = {
    "id": "mlx-whisper",
    "name": "mlx-whisper",
    "display_name": "mlx-whisper (Apple Silicon)",
    "pip_install": "'scribed[mlx]'",
    "import_name": "mlx_whisper",
    "license": "MIT",
    "is_local": True,
    "is_remote": False,
    "capabilities": ["word_timestamps", "translate"],
    "default_for": [],
    "api_env_var": "",
    "description": "OpenAI Whisper on Apple Silicon via MLX (macOS arm64 only).",
    "param_map": {
        "language": {"native_name": "language"},  # None => auto-detect
        "model": {"native_name": "model", "default": DEFAULT_MODEL},
        "word_timestamps": {"native_name": "word_timestamps", "default": False},
        "task": {"native_name": "task"},  # "transcribe" | "translate"
        "initial_prompt": {"native_name": "initial_prompt"},
        "diarize": None,  # not supported (use whisperx)
    },
}
