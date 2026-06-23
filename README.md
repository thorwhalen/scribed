# scribed

One façade over many speech-to-text (ASR) engines — plus a **ledger** to help you choose between them.

Transcription ("turn this audio into text") is solved a dozen ways: local engines
(Whisper, faster-whisper, whisper.cpp, Vosk), fast cheap cloud APIs (Groq, OpenAI),
and feature-rich premium services (Deepgram, AssemblyAI, Google, ElevenLabs) —
each with its own install, API, pricing, latency, language coverage, and
diarization quirks. `scribed` gives you a uniform call, a browsable catalog of
every option, and the tools to wrap any of them.

```python
import scribed

text = scribed.transcribe_text("talk.mp3")     # just the text, default backend
t = scribed.transcribe("talk.mp3")             # full result: text + timed segments
print(t)                                       # -> the transcript
print(t.srt)                                   # -> SRT subtitles
for seg in t:
    print(seg.start, seg.speaker, seg.text)    # iterate timed (optionally diarized) segments
```

The same call, the same `Transcript` back, no matter which engine ran.

## Install

`import scribed` is dependency-free. Install only the backends you use, via extras:

```bash
pip install "scribed[faster-whisper]"   # local, free — recommended default
pip install "scribed[whispercpp]"       # local, free, light (great on Apple Silicon)
pip install "scribed[vosk]"             # local, free, streaming/offline
pip install "scribed[openai]"           # cloud API (whisper-1 / gpt-4o-transcribe)
pip install "scribed[groq]"             # cloud API — fastest & cheapest hosted Whisper
pip install "scribed[deepgram]"         # cloud API — real-time + diarization
pip install "scribed[cli]"              # the `scribed` command
```

## Backends that ship today

| Backend | `backend=` id | Local / Remote | Cost | Diarize | Stream | Notable |
|---|---|---|---|---|---|---|
| faster-whisper | `faster-whisper` | local | free | – | – | **Recommended local default** — Whisper via CTranslate2, no system ffmpeg |
| OpenAI Whisper | `whisper` | local | free | – | – | The reference PyTorch Whisper (needs system ffmpeg) |
| whisper.cpp | `whispercpp` | local | free | – | ~ | Pure C/C++ — light, excellent on Apple Silicon / edge |
| Vosk | `vosk` | local | free | ~ | ✓ | Fully offline, streaming, tiny models (Raspberry Pi / mobile) |
| OpenAI | `openai` | remote | paid | – | ✓ | Simple & ubiquitous; whisper-1 / gpt-4o-transcribe |
| Groq | `groq` | remote | free tier | – | – | Fastest & cheapest hosted Whisper (OpenAI-compatible) |
| Deepgram | `deepgram` | remote | free tier | ✓ | ✓ | Nova-3: real-time + diarization, cheap, feature-rich |
| AssemblyAI | `assemblyai` | remote | free tier | ✓ | ✓ | Audio intelligence (diarization, sentiment, topics, summary) |
| Google STT | `google-speech` | remote | free tier | ✓ | ✓ | Widest language coverage (125+); Chirp models |
| ElevenLabs | `elevenlabs` | remote | free tier | ✓ | ~ | Scribe v1 — top accuracy, diarization, audio-event tags |

…plus more engines catalogued in the ledger (NVIDIA Parakeet/Canary, WhisperX,
wav2vec2, Moonshine, sherpa-onnx, AWS Transcribe, Azure Speech, Speechmatics,
Gladia, Rev, Fireworks, Cloudflare …) that you can turn into a working façade
with one command (see *Add a backend* below).

### Getting a backend running

Some backends need more than `pip install` (Whisper's *system* ffmpeg, GPU wheels,
first-run model weights, or an API key). scribed turns that into structured,
OS-aware guidance — handy for humans and AI agents alike:

```python
scribed.doctor()                       # what's usable now vs what each missing one needs
scribed.check("faster-whisper")        # -> True/False (usable right now?)
print(scribed.requirements("whisper").instructions())   # exact plan: system deps + pip + weights
scribed.install("faster-whisper", yes=True)             # plan, or actually run the pip install
```

## The ledger — choose with eyes open

The catalog describes *every* engine we researched, not only the ones with a
working façade. It lives in data (`scribed/data/backends.json`), not code, so you
can read, filter, diff, and extend it:

```python
scribed.catalog                                   # the whole ledger
scribed.find(is_local=True, open_source=True)     # only local OSS engines
scribed.find(diarization="yes", is_remote=True)   # speaker-labelling cloud APIs
scribed.find(implemented=True)                    # only what scribed can run today
scribed.catalog.supports_language("French")       # engines that list French
scribed.catalog.to_dataframe()                    # browse as a pandas table
```

`implemented` is computed live from the registry, so the ledger can never lie
about what scribed can actually run.

## The result model

Every backend returns the same `Transcript` — progressive disclosure from "just
the text" to full structure:

```python
t = scribed.transcribe("interview.wav", backend="deepgram", diarize=True)

str(t)            # the full transcript text
t.text            # same string
t.language        # detected language
t.duration        # audio duration (seconds)
for seg in t:     # Segment: .text .start .end .speaker .confidence .words
    ...
t.words           # flattened word-level units (when the engine reports them)
t.speakers        # ['speaker_0', 'speaker_1', ...] when diarized
t.srt             # SRT subtitles
t.vtt             # WebVTT subtitles
t.raw             # the untouched backend response
```

## Three tiers of access

```python
scribed.transcribe(audio)                                  # 1. facade, default backend
scribed.services.deepgram.transcribe(audio, diarize=True)  # 2. pick a backend explicitly
scribed.services.deepgram.adapter                          # 3. the raw engine adapter
```

## CLI

```bash
pip install "scribed[cli]"
scribed transcribe talk.mp3 --backend faster-whisper --output srt
scribed backends --capability diarize
scribed find --local --free --diarization
scribed status                 # readiness table: all ⊇ implemented ⊇ set-up ⊇ tested
scribed doctor                 # what's usable now, how to install the rest
scribed requirements whisper   # exact install plan
```

## Add a backend

The catalog is large; scribed ships a façade for a curated subset and gives you
the machinery (and a SKILL) to wrap any other in minutes:

```python
from scribed.make_backend import scaffold_backend, validate_adapter

scaffold_backend("speechmatics")     # generate scribed/backends/speechmatics/ from the ledger entry
# ...fill in param_map (config.py) and implement adapter.py's _transcribe...
validate_adapter("speechmatics")     # smoke-test it end to end
```

A backend is just a subpackage with a `config.py` (`BACKEND_CONFIG`) and an
`adapter.py` (`Adapter(BaseTranscriberAdapter)` implementing `_transcribe`). The
registry discovers it automatically; engine SDKs are imported lazily so
`import scribed` stays dependency-free.

## Design notes

- **Dependency-free import.** The base package declares no dependencies; every
  engine SDK is an optional extra, imported lazily inside its adapter.
- **Data-driven ledger.** Engine metadata is curated research in JSON, separate
  from code.
- **Normalized everything.** One input type (path / URL / bytes / file / numpy
  waveform), one result type (`Transcript`), one vocabulary of options translated
  per-engine via each backend's `param_map`.

`scribed` is the speech-to-text sibling of [`ocracy`](https://github.com/thorwhalen/ocracy)
(the same pattern for OCR).

## License

MIT
