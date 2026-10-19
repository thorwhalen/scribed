# scribed.backends.whisper.adapter

Adapter for the OpenAI Whisper (PyTorch) backend.

Maps scribed’s normalized request onto `whisper.load_model(...).transcribe(...)`
and the resulting result-dict onto a [`scribed.base.Transcript`](scribed.base.html.md#scribed.base.Transcript). The engine
and model are imported and constructed lazily so `import scribed` stays
dependency-free.

The reference Whisper decodes audio with a system `ffmpeg` and expects a real
file path, so in-memory inputs are first materialized via
[`scribed.util.ensure_file_path()`](scribed.util.html.md#scribed.util.ensure_file_path) (and cleaned up afterwards).

### Classes

| [`Adapter`](#scribed.backends.whisper.adapter.Adapter)(config)   | OpenAI Whisper (PyTorch) adapter (caches one model per requested size).   |
|--------------------------------------------------------------------|---------------------------------------------------------------------------|

### *class* scribed.backends.whisper.adapter.Adapter(config)

Bases: [`BaseTranscriberAdapter`](scribed.make_backend.html.md#scribed.make_backend.BaseTranscriberAdapter)

OpenAI Whisper (PyTorch) adapter (caches one model per requested size).
