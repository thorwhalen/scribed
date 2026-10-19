# scribed.backends.whisper.config

Configuration for the OpenAI Whisper (PyTorch) backend.

This is the original PyTorch reference implementation of Whisper
(`openai-whisper`), run fully locally. Unlike faster-whisper it requires a
system `ffmpeg` to decode audio, so the adapter always hands the engine a real
file path.

Model selection is read from the environment so the default just works, while
power users can tune it:

- `SCRIBED_WHISPER_MODEL` (default `"base"`; e.g. `small`, `large-v3`)

…or pass `model=` to a transcribe call. Word-level timestamps are available
(`word_timestamps=True`) and translation via `task="translate"`.
