# scribed.backends.faster_whisper.config

Configuration for the faster-whisper backend.

faster-whisper runs OpenAI’s Whisper models via CTranslate2 — fast, accurate, and
CPU-capable, with no system ffmpeg required (it decodes via bundled PyAV). This is
scribed’s default local engine.

Model selection (and device / compute type) are read from the environment so the
default just works, while power users can tune them:

- `SCRIBED_FASTER_WHISPER_MODEL` (default `"base"`; e.g. `small`, `large-v3`)
- `SCRIBED_FASTER_WHISPER_DEVICE` (default `"auto"`; `cpu` / `cuda`)
- `SCRIBED_FASTER_WHISPER_COMPUTE` (default `"default"`; e.g. `int8`, `float16`)

…or pass `model=` to a transcribe call.
