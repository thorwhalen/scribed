# scribed.backends.openai.config

Configuration for the OpenAI transcription backend.

Uses OpenAI’s hosted audio-transcriptions endpoint. `whisper-1` returns rich
`verbose_json` (segments + timing); the `gpt-4o-transcribe` /
`gpt-4o-mini-transcribe` models return text/json only (no segment timing).
