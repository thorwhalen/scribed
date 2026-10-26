# scribed.backends.mlx_whisper.config

Configuration for the mlx-whisper backend (Whisper on Apple Silicon via MLX).

[mlx-whisper](https://pypi.org/project/mlx-whisper/) is Apple’s (ml-explore)
port of OpenAI Whisper to MLX: it runs on the M-series GPU with unified memory, and
returns openai-whisper-shaped results (segments, optional word timestamps).
macOS on Apple Silicon only.

`model` is either a Hugging Face repo id (`"mlx-community/whisper-large-v3-turbo"`,
the default) or a bare Whisper size (`"tiny"`, `"base"`, `"small"`,
`"medium"`, `"large-v3"`, `"turbo"`), resolved by
[`scribed.backends.mlx_whisper.adapter.resolve_model_repo()`](scribed.backends.mlx_whisper.adapter.html.md#scribed.backends.mlx_whisper.adapter.resolve_model_repo).

### Module Attributes

| [`DEFAULT_MODEL`](#scribed.backends.mlx_whisper.config.DEFAULT_MODEL)   | Default MLX Whisper weights (fast and accurate on M2+).   |
|------------------------------------------------------------------|-----------------------------------------------------------|

### scribed.backends.mlx_whisper.config.DEFAULT_MODEL *= 'mlx-community/whisper-large-v3-turbo'*

Default MLX Whisper weights (fast and accurate on M2+).
