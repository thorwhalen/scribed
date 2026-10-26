# scribed.backends.parakeet_mlx.config

Configuration for the parakeet-mlx backend (NVIDIA Parakeet-TDT on Apple Silicon).

[parakeet-mlx](https://pypi.org/project/parakeet-mlx/) runs NVIDIA’s
Parakeet-TDT models on Apple Silicon via MLX: among the fastest accurate local
English (v2) / 25-European-language (v3) engines. macOS on Apple Silicon only.
The language is detected by the model itself (no `language` argument).

### Module Attributes

| [`DEFAULT_MODEL`](#scribed.backends.parakeet_mlx.config.DEFAULT_MODEL)   | multilingual, 25 European languages).   |
|------------------------------------------------------------------|-----------------------------------------|

### scribed.backends.parakeet_mlx.config.DEFAULT_MODEL *= 'mlx-community/parakeet-tdt-0.6b-v3'*

multilingual, 25 European languages).

* **Type:**
  Default Parakeet weights (v3
