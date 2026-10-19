# scribed.backends.assemblyai.adapter

Adapter for the AssemblyAI (Universal) transcription backend.

Maps scribed’s normalized request onto `assemblyai.Transcriber.transcribe` and
the returned transcript onto a [`scribed.base.Transcript`](scribed.base.html.md#scribed.base.Transcript). When speaker
labels are requested AssemblyAI returns `utterances` (one diarized speaker
turn each, with nested words); otherwise we build a single segment from the full
text and its word stream. AssemblyAI reports times in **milliseconds**, so we
divide by 1000 to get scribed’s seconds. The SDK and credential are resolved
lazily so `import scribed` stays dependency-free.

### Classes

| [`Adapter`](#scribed.backends.assemblyai.adapter.Adapter)(config)   | AssemblyAI (Universal) transcription adapter.   |
|--------------------------------------------------------------------|-------------------------------------------------|

### *class* scribed.backends.assemblyai.adapter.Adapter(config)

Bases: [`BaseTranscriberAdapter`](scribed.make_backend.html.md#scribed.make_backend.BaseTranscriberAdapter)

AssemblyAI (Universal) transcription adapter.
