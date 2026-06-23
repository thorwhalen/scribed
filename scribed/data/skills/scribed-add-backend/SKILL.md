---
name: scribed-add-backend
description: Add a new speech-to-text engine to scribed by writing a backend façade (config.py + adapter.py) that normalizes the engine into scribed's Transcript. Use when the user wants to wrap/support a transcription engine scribed doesn't implement yet (e.g. Speechmatics, NVIDIA Parakeet, AWS Transcribe, Azure Speech, a custom/in-house ASR), asks "how do I add a backend to scribed", or wants to scaffold/implement a new adapter.
---

# scribed — adding a backend

A backend is a subpackage of `scribed.backends` with two files:
`config.py` (a `BACKEND_CONFIG` dict) and `adapter.py` (`Adapter` with a
`transcribe(audio, **kwargs) -> Transcript`). The registry discovers it
automatically; the engine SDK must be imported **lazily** so `import scribed`
stays dependency-free.

## 1. Scaffold from the ledger

```python
from scribed.make_backend import scaffold_backend
scaffold_backend("speechmatics")     # creates scribed/backends/speechmatics/, pre-filled from the ledger entry
```

(If the engine isn't in the ledger, add a record to `scribed/data/backends.json`
first — see `scribed/data/SCHEMA.md` — or scaffold and fill `config.py` by hand.)

## 2. Fill `config.py`

```python
BACKEND_CONFIG = {
    "id": "speechmatics",
    "name": "Speechmatics",
    "display_name": "Speechmatics",
    "pip_install": "speechmatics-python",
    "import_name": "speechmatics",     # used to probe availability
    "license": "proprietary",
    "is_local": False,
    "is_remote": True,
    "capabilities": ["diarize", "word_timestamps"],   # beyond the implied "transcribe"
    "default_for": [],
    "api_env_var": "SPEECHMATICS_API_KEY",             # "" if local
    "description": "...",
    # Map scribed's normalized options -> the engine's native names (None = unsupported):
    "param_map": {
        "language": {"native_name": "language"},
        "diarize":  {"native_name": "diarization"},
        # "word_timestamps": None,   # explicitly unsupported -> clear warning
    },
}
```

Then register the extra in `pyproject.toml`:
`[project.optional-dependencies]  speechmatics = ["speechmatics-python>=..."]`.

## 3. Implement `adapter.py`

Subclass `BaseTranscriberAdapter` and implement `_transcribe` (it receives the
audio plus already-translated *native* kwargs):

```python
from scribed.base import Transcript
from scribed.make_backend import BaseTranscriberAdapter, make_segment, make_word

class Adapter(BaseTranscriberAdapter):
    def _transcribe(self, audio, **native_kwargs) -> Transcript:
        import the_engine                                    # lazy!
        from scribed.util import ensure_file_path, cleanup_temp, load_audio_bytes
        # remote: from scribed.credentials import resolve_credential
        #         key = resolve_credential("speechmatics", env_var=self.config.get("api_env_var"))

        path, is_temp = ensure_file_path(audio)              # or load_audio_bytes(audio) for REST
        try:
            native = the_engine.transcribe(path, **native_kwargs)
        finally:
            cleanup_temp(path, is_temp)

        segments = [
            make_segment(
                u.text, start=u.start, end=u.end, confidence=u.conf,  # times in SECONDS
                speaker=str(u.speaker) if u.speaker else None,        # set when diarized
                words=[make_word(w.text, start=w.start, end=w.end, confidence=w.conf) for w in u.words],
            )
            for u in native.utterances
        ]
        return Transcript.from_segments(segments, backend=self.backend_id, raw=native,
                                        language=native.language, duration=native.duration)
```

### Normalization rules

- **Times in seconds** (convert ms→/1000, centiseconds→/100, timedeltas→`.total_seconds()`).
- **Confidence in `[0,1]`** — pass `conf_scale=100` for percent scales, or `math.exp(logprob)`.
- **Diarization** → set `speaker=` (a string) on each `Segment` (and `Word`).
- Stash the engine's native response in `raw=`.

## 4. Validate

```python
from scribed.make_backend import validate_adapter
validate_adapter("speechmatics")     # smoke-tests end to end; for remotes this makes a real (billed) call
```

`validate_adapter` with no `audio=` uses a generated tone (a *wiring* test). Pass
`audio=<speech clip>` + `expect_text=...` to check real recognition. Then add the
engine to the README table.
