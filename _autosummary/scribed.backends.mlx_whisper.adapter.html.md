# scribed.backends.mlx_whisper.adapter

Adapter for the mlx-whisper backend (Whisper on Apple Silicon via MLX).

Decodes the input to a float32 mono 16 kHz array (no ffmpeg needed), calls
`mlx_whisper.transcribe(array, path_or_hf_repo=...)` and maps its
openai-whisper-shaped result dict onto a [`scribed.base.Transcript`](scribed.base.html.md#scribed.base.Transcript).
`mlx_whisper` is imported on first use, after the Apple-Silicon check, so this
module imports anywhere.

### Module Attributes

| [`MODEL_REPO_TEMPLATE`](#scribed.backends.mlx_whisper.adapter.MODEL_REPO_TEMPLATE)   | How a bare Whisper size maps to an `mlx-community` repo id.                                                          |
|------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------|
| [`MODEL_REPO_OVERRIDES`](#scribed.backends.mlx_whisper.adapter.MODEL_REPO_OVERRIDES)  | Sizes whose mlx-community repo does not follow [`MODEL_REPO_TEMPLATE`](#scribed.backends.mlx_whisper.adapter.MODEL_REPO_TEMPLATE). |

### Functions

| [`resolve_model_repo`](#scribed.backends.mlx_whisper.adapter.resolve_model_repo)(model)   | Resolve a model name to a Hugging Face repo id for `mlx_whisper`.   |
|------------------------------------------------------------------------------|---------------------------------------------------------------------|

### Classes

| [`Adapter`](#scribed.backends.mlx_whisper.adapter.Adapter)(config)   | mlx-whisper adapter (Apple Silicon only).   |
|--------------------------------------------------------------------|---------------------------------------------|

### *class* scribed.backends.mlx_whisper.adapter.Adapter(config)

Bases: [`BaseTranscriberAdapter`](scribed.make_backend.html.md#scribed.make_backend.BaseTranscriberAdapter)

mlx-whisper adapter (Apple Silicon only).

#### module_name *= 'mlx_whisper'*

Engine module name — the seam tests use to inject a fake backend.

### scribed.backends.mlx_whisper.adapter.MODEL_REPO_OVERRIDES *= {'large-v3-turbo': 'mlx-community/whisper-large-v3-turbo', 'turbo': 'mlx-community/whisper-large-v3-turbo'}*

Sizes whose mlx-community repo does not follow [`MODEL_REPO_TEMPLATE`](#scribed.backends.mlx_whisper.adapter.MODEL_REPO_TEMPLATE).

### scribed.backends.mlx_whisper.adapter.MODEL_REPO_TEMPLATE *= 'mlx-community/whisper-{model}-mlx'*

How a bare Whisper size maps to an `mlx-community` repo id.

### scribed.backends.mlx_whisper.adapter.resolve_model_repo(model)

Resolve a model name to a Hugging Face repo id for `mlx_whisper`.

```pycon
>>> resolve_model_repo("base")
'mlx-community/whisper-base-mlx'
>>> resolve_model_repo("turbo")
'mlx-community/whisper-large-v3-turbo'
>>> resolve_model_repo("someone/custom-whisper")
'someone/custom-whisper'
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
