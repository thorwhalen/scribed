# scribed.backends.vosk.config

Configuration for the Vosk (Kaldi) backend.

Vosk is an offline, streaming speech-recognition toolkit built on Kaldi. It runs
fully locally with no network call and supports incremental (chunked) decoding,
which makes it a good fit for low-latency / privacy-sensitive transcription.

Vosk needs **16 kHz mono 16-bit PCM** audio; the adapter handles resampling and
PCM conversion, so callers can pass any supported audio input.

Model selection:

- `SCRIBED_VOSK_MODEL` — if set, a filesystem path to an unpacked Vosk model
  directory (`Model(model_path=...)`). Preferred when present.
- Otherwise the adapter uses `Model(lang=<language>)` (default `"en-us"`),
  which auto-downloads a small model for that language on first use. The
  `language` request kwarg picks the lang code.
