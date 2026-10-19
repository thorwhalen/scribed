# scribed.backends.groq.adapter

Adapter for the Groq (hosted Whisper) transcription backend.

Groq’s audio-transcriptions API mirrors OpenAI’s, so this adapter is a close
sibling of [`scribed.backends.openai.adapter`](scribed.backends.openai.adapter.html.md#module-scribed.backends.openai.adapter): it maps scribed’s normalized
request onto `client.audio.transcriptions.create` and the `verbose_json`
response onto a [`scribed.base.Transcript`](scribed.base.html.md#scribed.base.Transcript). The Groq SDK and credential
are resolved lazily so `import scribed` stays dependency-free, and the audio is
sent as a `(filename, bytes)` tuple via [`scribed.util.load_audio_bytes()`](scribed.util.html.md#scribed.util.load_audio_bytes).

### Classes

| [`Adapter`](#scribed.backends.groq.adapter.Adapter)(config)   | Groq hosted-Whisper transcription adapter (client cached lazily).   |
|--------------------------------------------------------------------|---------------------------------------------------------------------|

### *class* scribed.backends.groq.adapter.Adapter(config)

Bases: [`BaseTranscriberAdapter`](scribed.make_backend.html.md#scribed.make_backend.BaseTranscriberAdapter)

Groq hosted-Whisper transcription adapter (client cached lazily).
