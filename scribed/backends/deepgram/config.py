"""Configuration for the Deepgram (Nova-3) transcription backend.

Deepgram's hosted speech-to-text API. Nova-3 is a fast, accurate model with
diarization, word-level timestamps, and streaming — ~$0.0043/min with diarization
and $200 of free credit on signup.

The native kwargs declared here (``model``, ``diarize``, ``language``) are
forwarded by the adapter into ``PrerecordedOptions``; the adapter additionally
sets ``smart_format``, ``punctuate`` and ``utterances`` so that diarized speaker
turns come back as ``results.utterances`` (one :class:`scribed.base.Segment`
each, carrying nested word-level timing).
"""

BACKEND_CONFIG = {
    "id": "deepgram",
    "name": "Deepgram",
    "display_name": "Deepgram (Nova-3)",
    "pip_install": "deepgram-sdk",
    "import_name": "deepgram",
    "license": "proprietary",
    "is_local": False,
    "is_remote": True,
    "capabilities": ["diarize", "word_timestamps", "stream"],
    "default_for": [],
    "api_env_var": "DEEPGRAM_API_KEY",
    "description": "Deepgram hosted transcription (Nova-3) with diarization, word timestamps, and streaming.",
    # Map normalized kwarg -> native kwarg config. These native names are popped
    # in the adapter's ``_transcribe`` and passed to ``PrerecordedOptions``.
    "param_map": {
        "language": {"native_name": "language"},  # None => auto-detect
        "diarize": {"native_name": "diarize"},
        "model": {"native_name": "model", "default": "nova-3"},
    },
}
