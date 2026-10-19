# scribed.backends.vosk.adapter

Adapter for the Vosk (Kaldi) backend.

Vosk is an offline Kaldi-based recognizer that decodes **16 kHz mono 16-bit PCM**
fed in chunks. This adapter reads any supported audio input as a float32 mono
waveform, resamples to 16 kHz when needed, converts to little-endian int16 PCM,
streams it through a `vosk.KaldiRecognizer`, and maps Vosk’s per-result
JSON (with `SetWords(True)` word timings/confidences) onto a
[`scribed.base.Transcript`](scribed.base.html.md#scribed.base.Transcript).

The engine SDK is imported lazily and the model is cached on the adapter so
`import scribed` stays dependency-free and repeated calls reuse the model.

Model selection:

- `SCRIBED_VOSK_MODEL` (a path to an unpacked model dir) is preferred when set.
- Otherwise `Model(lang=<language>)` (default `"en-us"`) auto-downloads a
  small model for the requested language on first use.

### Classes

| [`Adapter`](#scribed.backends.vosk.adapter.Adapter)(config)   | Vosk adapter (caches one model per requested language / model path).   |
|--------------------------------------------------------------------|------------------------------------------------------------------------|

### *class* scribed.backends.vosk.adapter.Adapter(config)

Bases: [`BaseTranscriberAdapter`](scribed.make_backend.html.md#scribed.make_backend.BaseTranscriberAdapter)

Vosk adapter (caches one model per requested language / model path).
