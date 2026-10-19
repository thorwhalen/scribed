# scribed.backends.assemblyai.config

Configuration for the AssemblyAI (Universal) transcription backend.

AssemblyAI is a hosted speech-to-text API built on its Universal model. It
provides speaker diarization (`speaker_labels`), word-level timestamps, and a
suite of audio-intelligence features (sentiment, topics, summarization, …).
The SDK uploads local files for you, so a transcribe call accepts either a local
file path or a publicly reachable URL.

The two normalized params scribed exposes here map onto
`assemblyai.TranscriptionConfig` fields: `language` -> `language_code` and
`diarize` -> `speaker_labels`. Additional native config (sentiment_analysis,
iab_categories, summarization, …) can be passed through and is forwarded to
`TranscriptionConfig` verbatim.
