# scribed.backends.parakeet_mlx.adapter

Adapter for the parakeet-mlx backend (NVIDIA Parakeet-TDT on Apple Silicon).

Loads a model with `parakeet_mlx.from_pretrained(repo)` (cached per repo),
transcribes a temporary audio file, and maps the returned `AlignedResult`’s
sentences (text + float-second `start`/`end`) onto scribed segments.
Parakeet’s tokens are sub-word pieces, so no word list is emitted.
`parakeet_mlx` is imported on first use, after the Apple-Silicon check.

### Classes

| [`Adapter`](#scribed.backends.parakeet_mlx.adapter.Adapter)(config)   | parakeet-mlx adapter (Apple Silicon only; caches one model per repo).   |
|--------------------------------------------------------------------|-------------------------------------------------------------------------|

### *class* scribed.backends.parakeet_mlx.adapter.Adapter(config)

Bases: [`BaseTranscriberAdapter`](scribed.make_backend.html.md#scribed.make_backend.BaseTranscriberAdapter)

parakeet-mlx adapter (Apple Silicon only; caches one model per repo).

#### module_name *= 'parakeet_mlx'*

Engine module name — the seam tests use to inject a fake backend.
