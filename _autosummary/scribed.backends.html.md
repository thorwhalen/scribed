# scribed.backends

Implemented speech-to-text backends.

Each real backend is a subpackage with a `config.py` (`BACKEND_CONFIG`) and an
`adapter.py` (`Adapter` with a `transcribe` method). The registry
([`scribed.registry`](scribed.registry.html.md#module-scribed.registry)) discovers them automatically. Subpackages whose name
starts with `_` (e.g. `scribed.backends._template`) are scaffolding
helpers, not real backends, and are skipped by discovery.

To add a backend, scaffold one from the template:

```default
from scribed.make_backend import scaffold_backend
scaffold_backend("speechmatics")   # creates scribed/backends/speechmatics/ from the template
```

### Modules

| [`assemblyai`](scribed.backends.assemblyai.html.md#module-scribed.backends.assemblyai)         | AssemblyAI backend for scribed.                   |
|--------------------------------------------------------------------------------------------------------|---------------------------------------------------|
| [`deepgram`](scribed.backends.deepgram.html.md#module-scribed.backends.deepgram)             | Deepgram (Nova-3) backend for scribed.            |
| [`elevenlabs`](scribed.backends.elevenlabs.html.md#module-scribed.backends.elevenlabs)         | ElevenLabs Scribe backend for scribed.            |
| [`faster_whisper`](scribed.backends.faster_whisper.html.md#module-scribed.backends.faster_whisper) | faster-whisper (CTranslate2) backend for scribed. |
| [`google_speech`](scribed.backends.google_speech.html.md#module-scribed.backends.google_speech)   | Google Cloud Speech-to-Text backend for scribed.  |
| [`groq`](scribed.backends.groq.html.md#module-scribed.backends.groq)                     | Groq (hosted Whisper) backend for scribed.        |
| [`openai`](scribed.backends.openai.html.md#module-scribed.backends.openai)                 | OpenAI transcription backend for scribed.         |
| [`vosk`](scribed.backends.vosk.html.md#module-scribed.backends.vosk)                     | Vosk (Kaldi) backend for scribed.                 |
| [`whisper`](scribed.backends.whisper.html.md#module-scribed.backends.whisper)               | OpenAI Whisper (PyTorch) backend for scribed.     |
| [`whispercpp`](scribed.backends.whispercpp.html.md#module-scribed.backends.whispercpp)         | whisper.cpp (pywhispercpp) backend for scribed.   |
