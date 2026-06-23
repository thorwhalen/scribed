---
name: scribed-install-backend
description: Get a scribed speech-to-text backend actually running — resolve its pip extra, system dependencies (e.g. ffmpeg), GPU wheels, first-run model weights, and API credentials. Use when transcription fails with a missing-dependency or missing-credential error, when the user asks "how do I install/set up <engine>", "scribed says backend not available", "ffmpeg not found", or "where do I get a Deepgram/AssemblyAI/OpenAI key".
---

# scribed — installing & setting up a backend

`import scribed` is dependency-free; each engine ships as an extra and is imported
lazily. When a backend isn't ready, scribed gives structured, OS-aware guidance.

## Diagnose

```python
import scribed
scribed.doctor()                 # {available: [...], missing: {id: hint}}
scribed.check("faster-whisper")  # True/False — usable right now?
scribed.status()                 # full readiness table (all ⊇ implemented ⊇ set_up ⊇ tested)
```

## Get the exact plan

```python
print(scribed.requirements("whisper").instructions())
# To use the 'whisper' backend:
#   1. System dependency: brew install ffmpeg   (openai-whisper needs the ffmpeg binary)
#   2. pip install "scribed[whisper]"
#   • Downloads the Whisper checkpoint on first use ...
```

`requirements(id, gpu=True)` adds GPU-wheel guidance. The `Requirements` object
also exposes structured fields: `.pip_command`, `.system`, `.gpu`, `.weights`,
`.credentials`, `.heavy`, `.alternative`.

## Install

```python
scribed.install("faster-whisper", yes=True)   # runs the pip install + verifies
# system deps and GPU wheels are SURFACED, never run automatically (they need sudo/brew/CUDA choices)
```

Or just `pip install "scribed[<extra>]"` yourself (see `requirements(...).pip_command`).

## Credentials (remote backends)

Set the env var named in the backend's config / guidance, e.g.:

```bash
export OPENAI_API_KEY=...        # openai
export GROQ_API_KEY=...          # groq
export DEEPGRAM_API_KEY=...      # deepgram
export ASSEMBLYAI_API_KEY=...    # assemblyai
export ELEVENLABS_API_KEY=...    # elevenlabs
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json   # google-speech
```

`scribed.requirements("deepgram").credentials` prints the var and a "get a key" link.
scribed also picks up a `.env` file if `python-dotenv` is installed.

## Common gotchas

- **`whisper` (openai-whisper)** needs the **system ffmpeg** binary. Prefer
  `faster-whisper` (no system ffmpeg, ~4× faster).
- **Local models download on first run** (cached under `~/.cache/...`).
- **`vosk`** needs a downloaded model dir; set `SCRIBED_VOSK_MODEL` or let it
  auto-download a small one.
- **Remote backends** can pass `check()` (library importable) but still be
  *not set up* until their credential env var is present.
