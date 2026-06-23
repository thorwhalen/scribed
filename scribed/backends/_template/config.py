"""Configuration for the Template backend (copy-me).

``scaffold_backend`` rewrites the lines tagged ``# TEMPLATE`` from a ledger entry.
Everything else you fill in by hand: the ``param_map`` is where you map scribed's
normalized argument names (``language``, ``diarize``, ``word_timestamps``, ...)
onto the engine's native parameter names. See ``scribed/data/SCHEMA.md`` for field
meanings.
"""

BACKEND_CONFIG = {
    "id": "__template__",  # TEMPLATE
    "name": "__template__",  # TEMPLATE
    "display_name": "Template Backend",  # TEMPLATE
    "pip_install": "PACKAGE",  # TEMPLATE  e.g. "faster-whisper"
    "import_name": "PACKAGE",  # TEMPLATE  module used to probe availability
    "license": "unknown",  # TEMPLATE
    "is_local": False,  # TEMPLATE
    "is_remote": False,  # TEMPLATE
    # Capabilities BEYOND the implied primary "transcribe" (audio -> text):
    # e.g. "diarize", "stream", "translate", "word_timestamps".
    "capabilities": [],
    # Capabilities this backend should be the *default* for (usually
    # ["transcribe"] for your first/most general engine).
    "default_for": [],
    # For remote backends: the env var(s) holding the credential, else "".
    "api_env_var": "",
    "description": "One-line description of the engine.",  # TEMPLATE
    # Map normalized kwarg -> native kwarg config (or None if unsupported):
    #   {"native_name": "language", "default": None, "coerce": <callable>}
    "param_map": {
        "language": {"native_name": "language"},
    },
}
