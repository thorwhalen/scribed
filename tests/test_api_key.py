"""A remote backend can be handed its API key (no environment needed). No network."""

import sys
import types

import pytest

from scribed import registry
from scribed.base import Transcript

REMOTE = ["assemblyai", "deepgram", "elevenlabs", "groq", "openai"]


@pytest.fixture(autouse=True)
def no_env_keys(monkeypatch):
    import scribed.credentials as creds

    for names in creds.PROVIDER_ENV_VARS.values():
        for name in names:
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(creds, "_soft_load_dotenv", lambda: None)


def _adapter(backend_id, **config):
    mod = __import__(f"scribed.backends.{backend_id}.adapter", fromlist=["Adapter"])
    return mod.Adapter({**registry.get_config(backend_id), **config})


@pytest.mark.parametrize("backend_id", REMOTE)
def test_config_api_key_wins_over_environment(backend_id, monkeypatch):
    env = registry.get_config(backend_id)["api_env_var"]
    env = env if isinstance(env, str) else env[0]
    monkeypatch.setenv(env, "from-env")
    assert _adapter(backend_id, api_key="handed").credential() == "handed"
    assert _adapter(backend_id).credential() == "from-env"


@pytest.mark.parametrize("backend_id", REMOTE)
def test_no_key_anywhere_still_raises_guidance(backend_id):
    from scribed.credentials import MissingCredentialError

    with pytest.raises(MissingCredentialError):
        _adapter(backend_id).credential()


def test_elevenlabs_transcribe_api_key_option_reaches_the_client(monkeypatch):
    seen = []

    class FakeClient:
        def __init__(self, api_key=None):
            seen.append(api_key)
            self.speech_to_text = types.SimpleNamespace(
                convert=lambda **kw: types.SimpleNamespace(text="hi", words=[])
            )

    pkg = types.ModuleType("elevenlabs")
    sub = types.ModuleType("elevenlabs.client")
    sub.ElevenLabs = FakeClient
    monkeypatch.setitem(sys.modules, "elevenlabs", pkg)
    monkeypatch.setitem(sys.modules, "elevenlabs.client", sub)

    adapter = _adapter("elevenlabs")
    t = adapter.transcribe(b"RIFFfake", api_key="per-call-key")
    assert isinstance(t, Transcript) and t.text == "hi"
    assert seen == ["per-call-key"]
    assert adapter.config.get("api_key") is None  # the shared adapter never held it
    assert adapter._client is None  # ... nor cached a client built with it


def test_local_backends_do_not_swallow_api_key():
    adapter = _adapter("vosk")
    assert adapter._takes_api_key is False
