"""Transcribing from an address (the service fetches it) and word times from hosted services.

All offline: fake SDK clients record what they are sent.
"""

import sys
import types

import pytest

import scribed
from scribed import registry
from scribed.backends._verbose_json import verbose_json_to_transcript
from scribed.base import TimeSpan

URL = "https://example.org/episode.mp3"

VERBOSE = {
    "text": "Rates rise. Maybe not.",
    "language": "en",
    "duration": 4.0,
    "segments": [
        {"start": 0.0, "end": 2.0, "text": "Rates rise.", "avg_logprob": -0.1},
        {"start": 2.0, "end": 4.0, "text": "Maybe not.", "avg_logprob": -0.2},
    ],
    "words": [
        {"word": "Rates", "start": 0.0, "end": 0.5},
        {"word": "rise.", "start": 0.5, "end": 1.9},
        {"word": "Maybe", "start": 2.1, "end": 2.6},
        {"word": "not.", "start": 2.6, "end": 3.9},
    ],
}


@pytest.fixture(autouse=True)
def key_env(monkeypatch):
    for name in ("GROQ_API_KEY", "ELEVENLABS_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setenv(name, "test-key")


def _fresh_client(monkeypatch, backend_id):
    """The shared adapter caches its client: drop it so this test's fake is used."""
    monkeypatch.setattr(scribed.services[backend_id].adapter, "_client", None)


@pytest.fixture
def no_download(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the audio must not be downloaded")

    monkeypatch.setattr("scribed.util._fetch_url", boom)


def _fake_groq(monkeypatch, answer=VERBOSE):
    calls = []

    class Groq:
        def __init__(self, api_key=None):
            transcriptions = types.SimpleNamespace(
                create=lambda **kw: calls.append(kw) or answer
            )
            self.audio = types.SimpleNamespace(transcriptions=transcriptions)

    monkeypatch.setitem(sys.modules, "groq", types.SimpleNamespace(Groq=Groq))
    _fresh_client(monkeypatch, "groq")
    return calls


def _fake_elevenlabs(monkeypatch):
    calls = []
    words = [
        types.SimpleNamespace(
            text=t, type="word", start=a, end=b, speaker_id=s, logprob=None
        )
        for t, a, b, s in [
            ("Hi", 0.0, 0.4, "speaker_0"),
            ("there", 0.5, 0.9, "speaker_1"),
        ]
    ]
    resp = types.SimpleNamespace(
        text="Hi there", words=words, language_code="en", audio_duration_secs=1.0
    )

    class ElevenLabs:
        def __init__(self, api_key=None):
            convert = lambda **kw: calls.append(kw) or resp  # noqa: E731
            self.speech_to_text = types.SimpleNamespace(convert=convert)

    client = types.ModuleType("elevenlabs.client")
    client.ElevenLabs = ElevenLabs
    monkeypatch.setitem(sys.modules, "elevenlabs", types.ModuleType("elevenlabs"))
    monkeypatch.setitem(sys.modules, "elevenlabs.client", client)
    _fresh_client(monkeypatch, "elevenlabs")
    return calls


def test_groq_by_address_sends_the_url_and_returns_word_times(monkeypatch, no_download):
    calls = _fake_groq(monkeypatch)
    t = scribed.transcribe(URL, backend="groq", word_timestamps=True)
    (sent,) = calls
    assert sent["url"] == URL and "file" not in sent
    assert sent["timestamp_granularities"] == ["word", "segment"]
    assert [s.text for s in t] == ["Rates rise.", "Maybe not."]
    assert [w.text for w in t.words] == ["Rates", "rise.", "Maybe", "not."]
    assert [w.text for w in t.segments[1].words] == ["Maybe", "not."]
    assert t.words[2].span == TimeSpan(2100, 2600)


def test_elevenlabs_by_address_sends_cloud_storage_url_with_speakers(
    monkeypatch, no_download
):
    calls = _fake_elevenlabs(monkeypatch)
    t = scribed.transcribe(URL, backend="elevenlabs", diarize=True)
    (sent,) = calls
    assert sent["cloud_storage_url"] == URL and "file" not in sent
    assert sent["diarize"] is True and sent["timestamps_granularity"] == "word"
    assert t.speakers == ["speaker_0", "speaker_1"] and len(t.words) == 2


def test_elevenlabs_http_address_is_downloaded_first(monkeypatch):
    calls = _fake_elevenlabs(monkeypatch)
    monkeypatch.setattr("scribed.util._fetch_url", lambda url, **k: b"RIFFbytes")
    scribed.transcribe("http://example.org/a.mp3", backend="elevenlabs")
    assert "file" in calls[0] and "cloud_storage_url" not in calls[0]


def test_remote_fetch_false_downloads_first(monkeypatch):
    calls = _fake_groq(monkeypatch)
    monkeypatch.setattr("scribed.util._fetch_url", lambda url, **k: b"RIFFbytes")
    scribed.transcribe(URL, backend="groq", remote_fetch=False)
    assert "file" in calls[0] and "url" not in calls[0]


def test_backend_without_the_capability_downloads_first(monkeypatch):
    assert "remote_fetch" not in registry.get_config("openai")["capabilities"]
    seen = []

    class OpenAI:
        def __init__(self, api_key=None):
            create = lambda **kw: seen.append(kw) or VERBOSE  # noqa: E731
            self.audio = types.SimpleNamespace(
                transcriptions=types.SimpleNamespace(create=create)
            )

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=OpenAI))
    _fresh_client(monkeypatch, "openai")
    monkeypatch.setattr("scribed.util._fetch_url", lambda url, **k: b"RIFFbytes")
    t = scribed.transcribe(URL, backend="openai", word_timestamps=True)
    assert "file" in seen[0] and "url" not in seen[0]
    assert seen[0]["timestamp_granularities"] == ["word", "segment"]
    assert len(t.words) == 4


def test_registry_tells_which_backends_fetch_and_which_return_word_times():
    assert set(scribed.list_backends("remote_fetch")) == {"groq", "elevenlabs"}
    assert {"groq", "openai", "elevenlabs"} <= set(
        scribed.list_backends("word_timestamps")
    )


def test_every_word_timestamps_backend_accepts_the_option_without_warning():
    import warnings

    from scribed.translation import make_kwargs_translator

    for backend_id in scribed.list_backends("word_timestamps"):
        translate = make_kwargs_translator(registry.get_config(backend_id)["param_map"])
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            translate(word_timestamps=True)


def test_verbose_json_words_without_segments_make_one_segment():
    resp = {
        "text": "a b",
        "words": [
            {"word": "a", "start": 0, "end": 1},
            {"word": "b", "start": 1, "end": 2},
        ],
    }
    t = verbose_json_to_transcript(resp, backend_id="x")
    assert len(t.segments) == 1 and [w.text for w in t.words] == ["a", "b"]
    assert t.segments[0].span == TimeSpan(0, 2000)


def test_verbose_json_without_words_is_as_before():
    resp = {k: v for k, v in VERBOSE.items() if k != "words"}
    t = verbose_json_to_transcript(resp, backend_id="x")
    assert [s.text for s in t] == ["Rates rise.", "Maybe not."] and t.words == []
