"""Configuration for the WhisperX backend.

`WhisperX <https://github.com/m-bain/whisperX>`_ = batched faster-whisper +
wav2vec2 forced alignment (accurate word timestamps) + optional pyannote speaker
diarization, in one pass — the sweet spot for multi-speaker meetings.

Diarization is off by default (speakers are a separate concern here —
see a dedicated diarizer); pass ``diarize=True`` to have WhisperX label
speakers. It needs a Hugging Face token (env ``HF_TOKEN``) that has accepted the
pyannote model terms. ``device``/``compute_type`` default to CUDA + float16 when a
GPU is visible, else CPU + int8.
"""

#: Default Whisper model size for WhisperX.
DEFAULT_MODEL = "large-v3"

#: Env var(s) holding the Hugging Face token pyannote diarization needs.
HF_TOKEN_ENV_VARS = ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN")

BACKEND_CONFIG = {
    "id": "whisperx",
    "name": "whisperx",
    "display_name": "WhisperX (align + diarize)",
    "pip_install": "'scribed[whisperx]'",
    "import_name": "whisperx",
    "license": "BSD-2-Clause",
    "is_local": True,
    "is_remote": False,
    "capabilities": ["word_timestamps", "diarize"],
    "default_for": [],
    "api_env_var": "",
    "description": "WhisperX: batched Whisper + word alignment + optional pyannote diarization.",
    "param_map": {
        "language": {"native_name": "language"},  # None => auto-detect
        "model": {"native_name": "model", "default": DEFAULT_MODEL},
        "diarize": {"native_name": "diarize", "default": False},
        "align": {"native_name": "align", "default": True},
        "batch_size": {"native_name": "batch_size", "default": 16},
        "device": {"native_name": "device"},  # None => cuda if available else cpu
        "compute_type": {"native_name": "compute_type"},  # None => by device
        "min_speakers": {"native_name": "min_speakers"},
        "max_speakers": {"native_name": "max_speakers"},
    },
}
