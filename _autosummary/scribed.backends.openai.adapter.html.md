# scribed.backends.openai.adapter

Adapter for the OpenAI transcription backend.

Maps scribed’s normalized request onto `client.audio.transcriptions.create` and
the response onto a [`scribed.base.Transcript`](scribed.base.html.md#scribed.base.Transcript). The client and credential
are resolved lazily so `import scribed` stays dependency-free.

### Classes

| [`Adapter`](#scribed.backends.openai.adapter.Adapter)(config)   | OpenAI transcription adapter.   |
|--------------------------------------------------------------------|---------------------------------|

### *class* scribed.backends.openai.adapter.Adapter(config)

Bases: [`BaseTranscriberAdapter`](scribed.make_backend.html.md#scribed.make_backend.BaseTranscriberAdapter)

OpenAI transcription adapter.
