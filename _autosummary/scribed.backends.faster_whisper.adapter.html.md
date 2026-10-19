# scribed.backends.faster_whisper.adapter

Adapter for the faster-whisper backend.

Maps scribed’s normalized request onto `faster_whisper.WhisperModel` and
its native `Segment`/`Word` stream onto a [`scribed.base.Transcript`](scribed.base.html.md#scribed.base.Transcript).
The engine and model are imported and constructed lazily so `import scribed`
stays dependency-free.

### Classes

| [`Adapter`](#scribed.backends.faster_whisper.adapter.Adapter)(config)   | faster-whisper adapter (caches one model per requested size).   |
|--------------------------------------------------------------------|-----------------------------------------------------------------|

### *class* scribed.backends.faster_whisper.adapter.Adapter(config)

Bases: [`BaseTranscriberAdapter`](scribed.make_backend.html.md#scribed.make_backend.BaseTranscriberAdapter)

faster-whisper adapter (caches one model per requested size).
