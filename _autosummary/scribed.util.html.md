# scribed.util

Audio-input normalization and small shared helpers.

Different ASR backends want their input in different forms: a filesystem path
(local Whisper, faster-whisper — they shell out to ffmpeg), raw `bytes` or a
file object (most cloud REST APIs), or a numpy waveform (deep-learning engines).
Callers, meanwhile, want to pass whatever they have — a path, an `http(s)` URL,
bytes, a file-like object, or a numpy array. This module bridges the two with a
handful of converters that **lazily** import soundfile / numpy / urllib only when
actually exercised, so `import scribed` stays dependency-free.

The key converters:

- [`load_audio_bytes()`](#scribed.util.load_audio_bytes) — anything -> encoded audio `bytes` (for REST APIs).
- [`ensure_file_path()`](#scribed.util.ensure_file_path) — anything -> a path on disk (writing a temp file for
  in-memory inputs); pair with [`cleanup_temp()`](#scribed.util.cleanup_temp) or use [`audio_path()`](#scribed.util.audio_path).
- [`audio_path()`](#scribed.util.audio_path) — a context manager yielding a path and cleaning up.
- [`to_waveform()`](#scribed.util.to_waveform) — anything -> `(numpy float32 mono, sample_rate)`.

### Functions

| [`classify_input`](#scribed.util.classify_input)(audio)                              | Classify an audio input as `url`/`path`/`bytes`/`file`/`numpy`.                                                         |
|-----------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------|
| [`is_url`](#scribed.util.is_url)(x)                                          | True if `x` is a string that looks like an http(s) URL.                                                                 |
| [`load_audio_bytes`](#scribed.util.load_audio_bytes)(audio, \*[, sample_rate])         | Return encoded audio `bytes` for any supported input.                                                                   |
| [`ensure_file_path`](#scribed.util.ensure_file_path)(audio, \*[, suffix, sample_rate]) | Return `(path, is_temp)` for any supported input.                                                                       |
| [`cleanup_temp`](#scribed.util.cleanup_temp)(path, is_temp)                        | Delete `path` iff `is_temp` (the flag returned by [`ensure_file_path()`](#scribed.util.ensure_file_path)). |
| [`audio_path`](#scribed.util.audio_path)(audio, \*[, suffix])                    | Context manager yielding a filesystem path for `audio`, cleaning up temps.                                              |
| [`to_waveform`](#scribed.util.to_waveform)(audio, \*[, sample_rate])              | Convert any supported input into `(numpy float32 mono, sample_rate)`.                                                   |
| [`check_import`](#scribed.util.check_import)(module_name, \*, install_hint[, ...]) | Import `module_name` or raise a friendly, actionable ImportError.                                                       |

### scribed.util.audio_path(audio, , suffix='.wav')

Context manager yielding a filesystem path for `audio`, cleaning up temps.

Example:

```default
with audio_path(raw_bytes) as p:
    segments = model.transcribe(p)
```

* **Return type:**
  [`Iterator`](https://docs.python.org/3/library/typing.html#typing.Iterator)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### scribed.util.check_import(module_name, , install_hint, feature='this')

Import `module_name` or raise a friendly, actionable ImportError.

Centralizes the “you need to `pip install X`” guidance so adapters and
converters don’t each hand-roll it.

### scribed.util.classify_input(audio)

Classify an audio input as `url`/`path`/`bytes`/`file`/`numpy`.

Decided structurally (and via duck typing for file objects / numpy) so we
never import soundfile or numpy just to look at the input.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### scribed.util.cleanup_temp(path, is_temp)

Delete `path` iff `is_temp` (the flag returned by [`ensure_file_path()`](#scribed.util.ensure_file_path)).

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### scribed.util.ensure_file_path(audio, , suffix='.wav', sample_rate=16000)

Return `(path, is_temp)` for any supported input.

Existing on-disk paths are returned untouched (`is_temp=False`). In-memory
inputs (bytes/URL/file/numpy) are written to a temp file (`is_temp=True`);
the caller is responsible for cleanup (use [`cleanup_temp()`](#scribed.util.cleanup_temp), or prefer
the [`audio_path()`](#scribed.util.audio_path) context manager).

* **Return type:**
  [`Tuple`](https://docs.python.org/3/library/typing.html#typing.Tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`bool`](https://docs.python.org/3/builtins/functions.html#bool)]

### scribed.util.is_url(x)

True if `x` is a string that looks like an http(s) URL.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### scribed.util.load_audio_bytes(audio, , sample_rate=16000)

Return encoded audio `bytes` for any supported input.

Pass-through for `bytes`; reads files and file objects; fetches URLs;
encodes numpy waveforms as WAV (at `sample_rate`).

* **Return type:**
  [`bytes`](https://docs.python.org/3/builtins/stdtypes.html#bytes)

### scribed.util.to_waveform(audio, , sample_rate=16000)

Convert any supported input into `(numpy float32 mono, sample_rate)`.

Numpy input is returned as-is (paired with `sample_rate`). Everything else
is decoded with soundfile and resampled is *not* performed — the returned
sample rate is whatever the source had (numpy inputs excepted).
