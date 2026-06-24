"""OpenAI backend adapter: response -> Transcript mapping, with an injected client.

No network. Mirrors the verbose_json / single-text mapping coverage that lived in
the `hearing` package before speech-to-text was centralized in scribed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("numpy")
pytest.importorskip("soundfile")

from scribed import registry
from scribed.backends.openai.adapter import Adapter
from scribed.base import TimeSpan, Transcript
from scribed.make_backend import make_test_audio


class _Seg:
    def __init__(self, start, end, text, avg_logprob=None):
        self.start = start
        self.end = end
        self.text = text
        self.avg_logprob = avg_logprob
        self.no_speech_prob = None


class _Resp:
    def __init__(self, *, segments=None, text="", language=None, duration=None):
        self.segments = segments
        self.text = text
        self.language = language
        self.duration = duration


class _FakeClient:
    """Mimics ``openai.OpenAI`` enough for the adapter (captures kwargs, no network)."""

    def __init__(self, resp):
        self._resp = resp
        self.captured: dict = {}
        client = self

        class _Transcriptions:
            def create(_inner, **kw):
                client.captured = kw
                return client._resp

        class _Audio:
            transcriptions = _Transcriptions()

        self.audio = _Audio()


def _adapter(resp) -> Adapter:
    adapter = Adapter(registry.get_config("openai"))
    adapter._client = _FakeClient(resp)  # inject; bypasses _get_client / network
    return adapter


def test_openai_maps_verbose_json_segments():
    resp = _Resp(
        segments=[_Seg(0.0, 1.5, "hello"), _Seg(1.5, 3.0, "world")],
        text="hello world",
        language="en",
        duration=3.0,
    )
    t = _adapter(resp)._transcribe(make_test_audio(), model="whisper-1")
    assert isinstance(t, Transcript)
    assert [s.text for s in t.segments] == ["hello", "world"]
    assert t.segments[0].span == TimeSpan(0, 1500)  # float seconds -> integer ms
    assert t.segments[1].span == TimeSpan(1500, 3000)
    assert t.text == "hello world" and t.language == "en" and t.duration == 3.0


def test_openai_falls_back_to_single_text():
    t = _adapter(_Resp(segments=None, text="just text"))._transcribe(
        make_test_audio(), model="gpt-4o-transcribe"
    )
    assert t.text == "just text"
    assert list(t.segments) == []  # no timed segments


def test_openai_requests_verbose_json_only_for_whisper1():
    a1 = _adapter(_Resp(text="x"))
    a1._transcribe(make_test_audio(), model="whisper-1")
    assert a1._client.captured.get("response_format") == "verbose_json"

    a2 = _adapter(_Resp(text="x"))
    a2._transcribe(make_test_audio(), model="gpt-4o-transcribe")
    assert "response_format" not in a2._client.captured  # gpt-4o has no segments
