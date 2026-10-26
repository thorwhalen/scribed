"""Configuration for the parakeet-mlx backend (NVIDIA Parakeet-TDT on Apple Silicon).

`parakeet-mlx <https://pypi.org/project/parakeet-mlx/>`_ runs NVIDIA's
Parakeet-TDT models on Apple Silicon via MLX: among the fastest accurate local
English (v2) / 25-European-language (v3) engines. macOS on Apple Silicon only.
The language is detected by the model itself (no ``language`` argument).
"""

#: Default Parakeet weights (v3: multilingual, 25 European languages).
DEFAULT_MODEL = "mlx-community/parakeet-tdt-0.6b-v3"

BACKEND_CONFIG = {
    "id": "parakeet-mlx",
    "name": "parakeet-mlx",
    "display_name": "Parakeet-TDT (Apple Silicon, MLX)",
    "pip_install": "'scribed[mlx]'",
    "import_name": "parakeet_mlx",
    "license": "Apache-2.0",
    "is_local": True,
    "is_remote": False,
    "capabilities": [],
    "default_for": [],
    "api_env_var": "",
    "description": "NVIDIA Parakeet-TDT on Apple Silicon via MLX (macOS arm64 only).",
    "param_map": {
        "model": {"native_name": "model", "default": DEFAULT_MODEL},
        "language": None,  # the model detects the language itself
        "diarize": None,
    },
}
