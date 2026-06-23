"""Credential resolution for remote transcription backends.

Remote engines need an API key (or a path to a service-account JSON). Rather than
make each adapter reinvent the lookup, this module centralizes a small, layered
resolver:

1. an explicit value passed by the caller (``api_key=...``),
2. the backend's declared environment variable(s),
3. (soft) a ``.env`` file discovered via ``python-dotenv`` if it is installed,
4. (optional) an interactive prompt, only in a REPL and only if asked.

A backend declares its variable(s) in ``BACKEND_CONFIG['api_env_var']`` (a string
or list). The well-known providers below give friendly defaults. The design
follows the credential pattern used by the sibling ``aix`` facade.
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional, Sequence, Union

__all__ = [
    "resolve_credential",
    "credential_help",
    "PROVIDER_ENV_VARS",
    "CREDENTIAL_GUIDANCE",
    "MissingCredentialError",
]

#: Friendly provider -> canonical env-var name(s) for well-known services.
PROVIDER_ENV_VARS = {
    "openai": ["OPENAI_API_KEY"],
    "groq": ["GROQ_API_KEY"],
    "deepgram": ["DEEPGRAM_API_KEY"],
    "assemblyai": ["ASSEMBLYAI_API_KEY"],
    "google-speech": ["GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_API_KEY"],
    "aws-transcribe": ["AWS_ACCESS_KEY_ID"],  # plus AWS_SECRET_ACCESS_KEY / region
    "azure-speech": ["AZURE_SPEECH_KEY"],
    "elevenlabs": ["ELEVENLABS_API_KEY", "ELEVEN_API_KEY"],
    "speechmatics": ["SPEECHMATICS_API_KEY"],
    "gladia": ["GLADIA_API_KEY"],
    "rev": ["REV_ACCESS_TOKEN"],
    "fireworks": ["FIREWORKS_API_KEY"],
}


#: Where/how to get a key, per provider — powers the dynamic "missing credential"
#: errors AND the README. Keep links current; these are user-facing.
CREDENTIAL_GUIDANCE = {
    "openai": {
        "env_var": "OPENAI_API_KEY",
        "get_key_url": "https://platform.openai.com/api-keys",
        "note": (
            "Create an API key in the OpenAI platform dashboard. Transcription "
            "uses whisper-1 / gpt-4o-transcribe at $0.006/min (whisper)."
        ),
    },
    "groq": {
        "env_var": "GROQ_API_KEY",
        "get_key_url": "https://console.groq.com/keys",
        "note": (
            "Create an API key in the Groq console. Groq serves whisper-large-v3 "
            "and turbo extremely fast and cheap (~$0.02-0.04/hr of audio)."
        ),
    },
    "deepgram": {
        "env_var": "DEEPGRAM_API_KEY",
        "get_key_url": "https://console.deepgram.com/signup",
        "note": (
            "Sign up and create an API key in the Deepgram console. Nova-3 is "
            "~$0.0043/min with diarization, streaming, and word timestamps; "
            "includes $200 free credit."
        ),
    },
    "assemblyai": {
        "env_var": "ASSEMBLYAI_API_KEY",
        "get_key_url": "https://www.assemblyai.com/dashboard/signup",
        "note": (
            "Create an account and copy your API key from the dashboard. "
            "Universal model with diarization, sentiment, topics; ~$0.0062/min "
            "(batch), free tier included."
        ),
    },
    "google-speech": {
        "env_var": "GOOGLE_APPLICATION_CREDENTIALS (or GOOGLE_API_KEY)",
        "get_key_url": "https://cloud.google.com/speech-to-text/docs/before-you-begin",
        "note": (
            "Create a Google Cloud project, enable the Speech-to-Text API, create "
            "a service account, download its JSON key, and point "
            "GOOGLE_APPLICATION_CREDENTIALS at that file. Chirp models, 125+ langs."
        ),
    },
    "aws-transcribe": {
        "env_var": "AWS_ACCESS_KEY_ID (plus AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION)",
        "get_key_url": "https://docs.aws.amazon.com/transcribe/latest/dg/getting-started.html",
        "note": (
            "Create AWS credentials (IAM user/role) with Transcribe permissions. "
            "Audio must usually be staged in S3 for batch jobs."
        ),
    },
    "azure-speech": {
        "env_var": "AZURE_SPEECH_KEY (plus AZURE_SPEECH_REGION)",
        "get_key_url": "https://learn.microsoft.com/azure/ai-services/speech-service/get-started-speech-to-text",
        "note": (
            "Create a Speech resource in the Azure portal; copy its key and "
            "region. Supports batch and real-time, diarization, custom models."
        ),
    },
    "elevenlabs": {
        "env_var": "ELEVENLABS_API_KEY",
        "get_key_url": "https://elevenlabs.io/app/settings/api-keys",
        "note": (
            "Create an API key in your ElevenLabs settings. Scribe v1 offers "
            "high-accuracy transcription with diarization and word timestamps."
        ),
    },
    "speechmatics": {
        "env_var": "SPEECHMATICS_API_KEY",
        "get_key_url": "https://portal.speechmatics.com/",
        "note": "Create an API key in the Speechmatics portal; batch + real-time.",
    },
    "gladia": {
        "env_var": "GLADIA_API_KEY",
        "get_key_url": "https://app.gladia.io/",
        "note": "Create an API key in the Gladia dashboard; Whisper-based API.",
    },
    "rev": {
        "env_var": "REV_ACCESS_TOKEN",
        "get_key_url": "https://www.rev.ai/access_token",
        "note": "Create an access token in the Rev AI console.",
    },
    "fireworks": {
        "env_var": "FIREWORKS_API_KEY",
        "get_key_url": "https://fireworks.ai/account/api-keys",
        "note": "Create an API key in the Fireworks dashboard; fast Whisper-v3.",
    },
}


def credential_help(provider: str) -> str:
    """A short, link-bearing 'how to get a key' message for ``provider`` (or '')."""
    g = CREDENTIAL_GUIDANCE.get(provider)
    if not g:
        return ""
    return (
        f"How to get a credential for {provider}: {g['note']} "
        f"Get a key: {g['get_key_url']}"
    )


class MissingCredentialError(RuntimeError):
    """Raised when a required credential cannot be resolved.

    Its message includes provider-specific, link-bearing guidance on how to
    obtain a key (see :data:`CREDENTIAL_GUIDANCE`).
    """


def _candidate_env_vars(
    provider: Optional[str], env_var: Optional[Union[str, Sequence[str]]]
) -> List[str]:
    names: List[str] = []
    if env_var:
        names.extend([env_var] if isinstance(env_var, str) else list(env_var))
    if provider and provider in PROVIDER_ENV_VARS:
        names.extend(PROVIDER_ENV_VARS[provider])
    # De-dup preserving order.
    seen, out = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _soft_load_dotenv() -> None:
    """Load a ``.env`` into the environment if python-dotenv is available."""
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        return
    load_dotenv()


def resolve_credential(
    provider: Optional[str] = None,
    *,
    api_key: Optional[str] = None,
    env_var: Optional[Union[str, Sequence[str]]] = None,
    required: bool = True,
    prompt_if_missing: bool = False,
) -> Optional[str]:
    """Resolve a credential for a remote backend.

    Args:
        provider: A known provider id (see :data:`PROVIDER_ENV_VARS`) used to
            infer default env-var names.
        api_key: An explicit value; if given, it wins and is returned as-is.
        env_var: Extra env-var name(s) to check (checked before provider defaults).
        required: If True (default), raise :class:`MissingCredentialError` when
            nothing resolves; if False, return ``None``.
        prompt_if_missing: If True and running interactively, prompt the user
            (via ``getpass``) as a last resort.

    Returns:
        The resolved secret, or ``None`` when ``required=False`` and nothing was
        found.
    """
    if api_key:
        return api_key

    candidates = _candidate_env_vars(provider, env_var)

    for name in candidates:
        val = os.environ.get(name)
        if val:
            return val

    # Soft .env discovery, then re-check.
    _soft_load_dotenv()
    for name in candidates:
        val = os.environ.get(name)
        if val:
            return val

    if prompt_if_missing and sys.stdin is not None and sys.stdin.isatty():
        import getpass

        label = candidates[0] if candidates else (provider or "API key")
        val = getpass.getpass(f"Enter credential for {label}: ").strip()
        if val:
            if candidates:
                os.environ[candidates[0]] = val
            return val

    if required:
        hint = f" (set one of: {', '.join(candidates)})" if candidates else ""
        guidance = credential_help(provider) if provider else ""
        msg = f"No credential found for {provider or 'backend'}{hint}."
        if guidance:
            msg += "\n" + guidance
        raise MissingCredentialError(msg)
    return None
