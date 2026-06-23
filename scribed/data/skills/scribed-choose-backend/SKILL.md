---
name: scribed-choose-backend
description: Choose the right speech-to-text engine for a transcription job using scribed's ledger — weigh local-vs-cloud, cost, speed, diarization, streaming, word timestamps, and language coverage. Use when the user asks "which transcription engine should I use", "what's the cheapest/fastest/most accurate STT", "do I need a cloud API or can I run it locally", "which one does speaker diarization", or wants to compare ASR options.
---

# scribed — choosing a backend

Use the ledger (`scribed.catalog`) to choose with eyes open. It describes every
engine scribed knows about, with `implemented` computed live from the registry.

## Decision shortcuts

```python
import scribed

# Free & private (no data leaves the machine):
scribed.find(is_local=True, open_source=True)
#   -> faster-whisper (best default), whisper, whispercpp (light/Apple Silicon),
#      vosk (streaming/offline/edge)

# Need speaker labels (who said what):
scribed.find(diarization="yes")            # deepgram, assemblyai, elevenlabs, google, ...

# Need real-time / streaming:
scribed.catalog.can("streaming")           # deepgram, assemblyai, vosk, google, azure, ...

# Cheapest hosted Whisper, very fast:
#   -> groq   (OpenAI-compatible, ~$0.02-0.11/hr)

# Widest language coverage:
#   -> google-speech (125+), or any Whisper engine (~99)
```

## Rules of thumb

- **Default local:** `faster-whisper` — fast, accurate, CPU-capable, no system ffmpeg.
- **Lightest local / Apple Silicon / edge:** `whispercpp`. **Offline streaming / tiny devices:** `vosk`.
- **Simplest cloud:** `openai`. **Fastest+cheapest cloud Whisper:** `groq`.
- **Production real-time + diarization + cheap:** `deepgram`.
- **Audio intelligence (sentiment/topics/summaries) + diarization:** `assemblyai`.
- **Top accuracy + diarization + audio tags:** `elevenlabs`. **Most languages / GCP:** `google-speech`.

## Compare side by side

```python
scribed.catalog.compare(["faster-whisper", "deepgram", "assemblyai"])
scribed.catalog.to_dataframe(columns=["name","is_local","pricing_model","diarization","streaming","languages_count"])
```

Pricing/coverage in the ledger are best-effort and change — verify against the
vendor before committing to a paid tier.
