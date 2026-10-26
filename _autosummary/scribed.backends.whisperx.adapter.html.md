# scribed.backends.whisperx.adapter

Adapter for the WhisperX backend (transcribe -> align -> optionally diarize).

Pipeline, on a float32 mono 16 kHz array (no ffmpeg needed):

1. `whisperx.load_model(model, device, compute_type=...)` (cached) then
   `.transcribe(audio, batch_size=..., language=...)`;
2. if `align`: `whisperx.load_align_model` + `whisperx.align` for accurate
   word timestamps;
3. if `diarize`: pyannote via WhisperX’s `DiarizationPipeline` +
   `whisperx.assign_word_speakers` (needs a Hugging Face token, env `HF_TOKEN`).

The result is openai-whisper-shaped, mapped by
`scribed.backends._whisper_common.whisper_result_to_segments()`. `whisperx` (and `torch`,
for device auto-detection) are imported on first use.

### Module Attributes

| [`DEFAULT_COMPUTE_TYPES`](#scribed.backends.whisperx.adapter.DEFAULT_COMPUTE_TYPES)   | `compute_type` used when none is given, by device.   |
|--------------------------------------------------------------------------|------------------------------------------------------|

### Classes

| [`Adapter`](#scribed.backends.whisperx.adapter.Adapter)(config)   | WhisperX adapter (caches ASR, alignment and diarization models).   |
|--------------------------------------------------------------------|--------------------------------------------------------------------|

### *class* scribed.backends.whisperx.adapter.Adapter(config)

Bases: [`BaseTranscriberAdapter`](scribed.make_backend.html.md#scribed.make_backend.BaseTranscriberAdapter)

WhisperX adapter (caches ASR, alignment and diarization models).

#### module_name *= 'whisperx'*

Engine module name — the seam tests use to inject a fake backend.

### scribed.backends.whisperx.adapter.DEFAULT_COMPUTE_TYPES *= {'cpu': 'int8', 'cuda': 'float16'}*

`compute_type` used when none is given, by device.
