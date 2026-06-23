---
name: scribed
description: Transcribe audio to text through one façade over many speech-to-text (ASR) engines — local (Whisper, faster-whisper, whisper.cpp, Vosk) and cloud (OpenAI, Groq, Deepgram, AssemblyAI, Google, ElevenLabs). Use when the user wants to transcribe speech/audio/a recording/a podcast/a meeting/a voice memo to text, get subtitles (SRT/VTT), diarize speakers, or choose between transcription engines. Triggers on "transcribe", "speech to text", "audio to text", "get subtitles", "who said what", "diarize".
---

# scribed — speech-to-text façade

`scribed` gives one uniform call over many ASR engines plus a ledger to choose
between them. `import scribed` is dependency-free; each engine is an optional
extra imported lazily.

## The one call

```python
import scribed

text = scribed.transcribe_text("talk.mp3")   # just the text
t = scribed.transcribe("talk.mp3")           # full Transcript
print(t.srt)                                 # SRT subtitles
for seg in t:                                # timed (optionally diarized) segments
    print(seg.start, seg.speaker, seg.text)
```

`transcribe(audio, *, backend=None, **options)` accepts a path, http(s) URL,
`bytes`, a file object, or a numpy waveform. With `backend=None` it picks the
first *installed* backend (faster-whisper is the flagged default). Normalized
options (`language=`, `diarize=`, `word_timestamps=`) are translated per engine;
unsupported ones warn and are dropped.

## The Transcript

`str(t)` / `t.text` (full text) · `t.language` · `t.duration` · iterate for
`Segment`s (`.text .start .end .speaker .confidence .words`) · `t.words` ·
`t.speakers` · `t.srt` / `t.vtt` · `t.raw`.

## Pick / discover a backend

```python
scribed.list_backends()                          # what's implemented
scribed.find(is_local=True, open_source=True)    # filter the ledger
scribed.find(diarization="yes")                  # speaker-labelling engines
scribed.services.deepgram.transcribe(a, diarize=True)   # use a specific backend
```

If a backend's dependency or key is missing you'll get a friendly install error.
See the **scribed-install-backend** skill for getting one running, the
**scribed-choose-backend** skill for picking the right engine, and the
**scribed-add-backend** skill for wrapping a new one.

## CLI (needs `pip install "scribed[cli]"`)

```bash
scribed transcribe talk.mp3 --backend faster-whisper --output srt
scribed find --local --free --diarization
scribed doctor          # what's usable now / how to install the rest
scribed status          # readiness table
```
