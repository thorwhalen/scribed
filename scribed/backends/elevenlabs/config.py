"""Configuration for the ElevenLabs Scribe transcription backend.

Uses ElevenLabs' hosted ``speech_to_text.convert`` endpoint with the
``scribe_v1`` model. Scribe returns the full text plus a flat ``words`` stream
(each word carrying ``start``/``end`` in seconds, a ``type`` of
``word``/``spacing``/``audio_event``, and — when ``diarize=True`` — a
``speaker_id``). There is no segment structure in the response; the adapter
builds segments by grouping consecutive ``word`` items by ``speaker_id``.
"""

BACKEND_CONFIG = {
    "id": "elevenlabs",
    "name": "ElevenLabs Scribe",
    "display_name": "ElevenLabs Scribe v1",
    "pip_install": "elevenlabs",
    "import_name": "elevenlabs",
    "license": "proprietary",
    "is_local": False,
    "is_remote": True,
    # Capabilities BEYOND the implied primary "transcribe" (audio -> text):
    "capabilities": ["diarize", "word_timestamps"],
    # Capabilities this backend should be the *default* for.
    "default_for": [],
    # For remote backends: the env var(s) holding the credential.
    "api_env_var": ["ELEVENLABS_API_KEY", "ELEVEN_API_KEY"],
    "description": (
        "ElevenLabs Scribe v1 hosted transcription with diarization and "
        "word-level timestamps."
    ),
    # Map normalized kwarg -> native kwarg config (or None if unsupported):
    "param_map": {
        "language": {"native_name": "language_code"},
        "diarize": {"native_name": "diarize", "default": False},
        "model": {"native_name": "model_id", "default": "scribe_v1"},
    },
}
