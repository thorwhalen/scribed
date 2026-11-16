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


def _fake_elevenlabs(monkeypatch):
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
    return seen


def test_with_api_key_reaches_the_client_once_and_never_the_shared_adapter(
    monkeypatch,
):
    from scribed.services import ServiceHandle

    seen = _fake_elevenlabs(monkeypatch)
    shared = ServiceHandle("elevenlabs")
    mine = shared.with_api_key("handed-key")
    for _ in range(3):  # a batch loop reuses one client
        t = mine.transcribe(b"RIFFfake")
    assert isinstance(t, Transcript) and t.text == "hi"
    assert seen == ["handed-key"]
    assert "api_key" not in registry.get_config("elevenlabs")
    assert shared.adapter.config.get("api_key") is None
    assert shared.adapter._client is None


@pytest.mark.parametrize("backend_id", ["vosk", "google-speech"])
def test_backends_that_cannot_take_a_key_say_so(backend_id):
    from scribed.services import ServiceHandle

    with pytest.raises(TypeError, match="API key"):
        ServiceHandle(backend_id).with_api_key("k")


def test_status_counts_a_key_registered_in_config(monkeypatch):
    from scribed import status

    monkeypatch.setattr(sys.modules["scribed.install"], "check", lambda b: True)
    cfg = registry.get_config("openai")
    assert status.is_set_up("openai") is False
    monkeypatch.setitem(cfg, "api_key", "k")
    assert status.is_set_up("openai") is True


def _fake_assemblyai(monkeypatch):
    made = []

    class Transcriber:
        def __init__(self, api_key=None):
            made.append({} if api_key is None else {"api_key": api_key})

        def transcribe(self, path, config=None):
            return types.SimpleNamespace(
                status="completed",
                error=None,
                text="hi",
                words=[],
                utterances=None,
                language_code="en",
            )

    aai = types.SimpleNamespace(
        settings=types.SimpleNamespace(api_key=None),
        Transcriber=Transcriber,
        TranscriptionConfig=lambda **kw: kw,
    )
    monkeypatch.setitem(sys.modules, "assemblyai", aai)
    return aai, made


def test_assemblyai_handed_key_is_scoped_not_global(monkeypatch):
    from scribed.services import ServiceHandle

    aai, made = _fake_assemblyai(monkeypatch)
    mine = ServiceHandle("assemblyai").with_api_key("handed")
    mine.transcribe(b"RIFFfake")
    mine.transcribe(b"RIFFfake")
    assert made == [{"api_key": "handed"}]  # one scoped transcriber, reused
    assert aai.settings.api_key is None  # the process-wide setting is untouched


def test_assemblyai_env_key_is_scoped_too_and_order_does_not_matter(monkeypatch):
    from scribed.services import ServiceHandle

    aai, made = _fake_assemblyai(monkeypatch)
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "from-env")
    _adapter("assemblyai").transcribe(b"RIFFfake")
    shared = ServiceHandle("assemblyai")
    shared.with_api_key("handed").transcribe(b"RIFFfake")
    assert made == [{"api_key": "from-env"}, {"api_key": "handed"}]
    assert aai.settings.api_key is None
    assert (
        shared.adapter._transcriber is None and "api_key" not in shared.adapter.config
    )
