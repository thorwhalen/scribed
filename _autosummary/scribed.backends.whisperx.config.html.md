# scribed.backends.whisperx.config

Configuration for the WhisperX backend.

[WhisperX](https://github.com/m-bain/whisperX) = batched faster-whisper +
wav2vec2 forced alignment (accurate word timestamps) + optional pyannote speaker
diarization, in one pass — the sweet spot for multi-speaker meetings.

Diarization is off by default (speakers are a separate concern here —
see a dedicated diarizer); pass `diarize=True` to have WhisperX label
speakers. It needs a Hugging Face token (env `HF_TOKEN`) that has accepted the
pyannote model terms. `device`/`compute_type` default to CUDA + float16 when a
GPU is visible, else CPU + int8.

### Module Attributes

| [`DEFAULT_MODEL`](#scribed.backends.whisperx.config.DEFAULT_MODEL)     | Default Whisper model size for WhisperX.                              |
|--------------------------------------------------------------------|-----------------------------------------------------------------------|
| [`HF_TOKEN_ENV_VARS`](#scribed.backends.whisperx.config.HF_TOKEN_ENV_VARS) | Env var(s) holding the Hugging Face token pyannote diarization needs. |

### scribed.backends.whisperx.config.DEFAULT_MODEL *= 'large-v3'*

Default Whisper model size for WhisperX.

### scribed.backends.whisperx.config.HF_TOKEN_ENV_VARS *= ('HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN')*

Env var(s) holding the Hugging Face token pyannote diarization needs.
