"""Tests for the scribed framework.

These exercise the engine-agnostic machinery — result types, the ledger/catalog,
the registry, parameter translation, install/status reporting — and require
neither a transcription engine nor a network connection. Backend *adapters* are
only checked for discovery and lazy importability, never actually run.
"""

import sys
import warnings

import pytest

import dataclasses

import scribed
from scribed.base import (
    Channel,
    Segment,
    TimeSpan,
    Transcript,
    Word,
    _format_timestamp,
)


# ---------------------------------------------------------------------------
# Import is dependency-free
# ---------------------------------------------------------------------------


def test_import_is_light():
    """Importing scribed exposes a version and core modules, no engine SDKs."""
    assert scribed.__version__
    assert "scribed.base" in sys.modules


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


def test_timespan():
    ts = TimeSpan(1000, 3500)  # integer milliseconds
    assert ts.duration_ms == 2500
    assert ts.as_seconds == (1.0, 3.5)
    assert TimeSpan.from_seconds(2.0, 4.0) == TimeSpan(2000, 4000)
    assert TimeSpan.from_seconds(2.0, 4.0).duration_ms == 2000
    assert TimeSpan(0, 1500).offset(500) == TimeSpan(500, 2000)


def test_segment_and_word_span():
    w = Word("hi", span=TimeSpan.from_seconds(0.0, 0.5), confidence=0.9)
    assert w.span == TimeSpan(0, 500)
    assert (w.start, w.end) == (0.0, 0.5)  # float-second convenience accessors
    s = Segment("hi there", span=TimeSpan.from_seconds(0.0, 1.0), words=(w,))
    assert s.span == TimeSpan(0, 1000)
    assert (s.start, s.end) == (0.0, 1.0)
    assert str(s) == "hi there"
    assert s.is_final is True  # batch segments are final by default
    assert s.channel is None  # generic STT leaves channel unset
    assert Word("x").span is None
    assert Word("x").start is None


def test_segment_streaming_and_channel_fields():
    """The spine's live-streaming + multi-source fields, enriched by frozen copy."""
    s = Segment("hi", span=TimeSpan(0, 500))
    interim = Segment("hi", span=TimeSpan(0, 500), is_final=False)
    assert interim.is_final is False

    spk = s.with_speaker("A")
    assert spk.speaker == "A" and s.speaker is None  # original untouched (frozen)

    ch = s.with_channel(Channel.MIC)
    assert ch.channel is Channel.MIC and s.channel is None
    assert Channel.MIC == "mic"  # str-enum wire value

    assert s.offset(1000).span == TimeSpan(1000, 1500)  # shift to absolute time
    assert Segment("x").offset(1000).span is None  # untimed stays untimed


def test_result_types_are_frozen():
    s = Segment("hi", span=TimeSpan(0, 500))
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.text = "no"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        TimeSpan(0, 1).start_ms = 5  # type: ignore[misc]


def test_transcript_basics():
    t = Transcript.from_segments(
        [
            Segment(
                "Hello there.",
                span=TimeSpan.from_seconds(0.0, 1.2),
                speaker="A",
                confidence=0.95,
            ),
            Segment(
                "General Kenobi.",
                span=TimeSpan.from_seconds(1.3, 2.8),
                speaker="B",
                confidence=0.85,
                words=(
                    Word("General", TimeSpan.from_seconds(1.3, 1.9)),
                    Word("Kenobi", TimeSpan.from_seconds(2.0, 2.8)),
                ),
            ),
        ],
        backend="demo",
        language="en",
        duration=2.8,
    )
    assert str(t) == "Hello there. General Kenobi."
    assert t.text == str(t)
    assert len(list(t)) == 2  # iterates segments
    assert t.speakers == ["A", "B"]
    assert t.at_speaker("A")[0].text == "Hello there."
    assert len(t.words) == 2
    assert abs(t.mean_confidence - 0.90) < 1e-9
    assert bool(t) is True
    assert t.duration == 2.8  # seconds field, unchanged
    assert t.duration_ms == 2800  # millisecond convenience accessor


def test_transcript_from_text():
    t = Transcript.from_text("just text", backend="x", language="en", duration=1.0)
    assert t.text == "just text"
    assert t.language == "en"
    assert t.duration == 1.0
    assert t.segments == ()  # frozen -> tuple, empty
    assert t.srt == ""  # no timed segments
    assert not Transcript.from_text("")


def test_filter_confidence():
    t = Transcript.from_segments(
        [
            Segment("keep", span=TimeSpan.from_seconds(0, 1), confidence=0.9),
            Segment("drop", span=TimeSpan.from_seconds(1, 2), confidence=0.3),
            Segment("nounce", span=TimeSpan.from_seconds(2, 3), confidence=None),
        ],
        backend="x",
    )
    kept = t.filter_confidence(0.5)
    assert [s.text for s in kept.segments] == ["keep"]
    assert kept.text == "keep"


# ---------------------------------------------------------------------------
# Subtitle export
# ---------------------------------------------------------------------------


def test_format_timestamp():
    assert _format_timestamp(0.0, comma=True) == "00:00:00,000"
    assert _format_timestamp(3.76, comma=True) == "00:00:03,760"
    assert _format_timestamp(3661.5, comma=False) == "01:01:01.500"


def test_srt_and_vtt():
    t = Transcript.from_segments(
        [
            Segment("Hello.", span=TimeSpan.from_seconds(0.0, 1.0), speaker="A"),
            Segment("World.", span=TimeSpan.from_seconds(1.0, 2.0)),
        ],
        backend="x",
    )
    srt = t.srt
    assert "1\n00:00:00,000 --> 00:00:01,000\n[A] Hello." in srt
    assert "2\n00:00:01,000 --> 00:00:02,000\nWorld." in srt
    vtt = t.vtt
    assert vtt.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:01.000" in vtt
    assert "<v A>Hello." in vtt


# ---------------------------------------------------------------------------
# Catalog / ledger
# ---------------------------------------------------------------------------


def test_catalog_loads():
    cat = scribed.catalog
    assert len(cat) >= 20
    assert "faster-whisper" in cat
    info = cat["faster-whisper"]
    assert info.is_local is True
    assert info.is_remote is False
    assert info.implemented is True  # computed live from registry


def test_catalog_filters():
    cat = scribed.catalog
    local_oss = cat.filter(is_local=True, open_source=True)
    assert "faster-whisper" in local_oss.ids
    assert "deepgram" not in local_oss.ids

    diarizers = cat.filter(diarization="yes")
    assert "deepgram" in diarizers.ids
    assert "faster-whisper" not in diarizers.ids

    # composes
    assert set(cat.filter(is_remote=True).filter(diarization="yes").ids) >= {
        "deepgram",
        "assemblyai",
    }


def test_catalog_can_capability():
    assert "vosk" in scribed.catalog.can("streaming").ids
    assert "deepgram" in scribed.catalog.can("diarization").ids


def test_find_facade():
    assert "faster-whisper" in scribed.find(implemented=True).ids
    assert set(scribed.find(is_local=True, open_source=True).ids) >= {
        "faster-whisper",
        "whisper",
        "vosk",
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


EXPECTED_BACKENDS = {
    "faster-whisper",
    "whisper",
    "whispercpp",
    "vosk",
    "openai",
    "groq",
    "deepgram",
    "assemblyai",
    "google-speech",
    "elevenlabs",
}


def test_registry_discovers_all_backends():
    impl = set(scribed.list_backends())
    assert EXPECTED_BACKENDS <= impl, f"missing: {EXPECTED_BACKENDS - impl}"


def test_template_is_not_a_backend():
    assert "__template__" not in scribed.list_backends()
    assert "_template" not in scribed.list_backends()


def test_get_config():
    cfg = scribed.get_config("deepgram")
    assert cfg["id"] == "deepgram"
    assert cfg["is_remote"] is True
    assert cfg["api_env_var"] == "DEEPGRAM_API_KEY"
    with pytest.raises(KeyError):
        scribed.get_config("nope")


def test_default_backend_prefers_flagged():
    # faster-whisper is flagged default_for transcribe.
    assert scribed.get_default_backend(require_available=False) == "faster-whisper"


def test_every_backend_config_is_wellformed():
    for bid in scribed.list_backends():
        cfg = scribed.get_config(bid)
        assert cfg.get("id") == bid
        assert isinstance(cfg.get("is_local"), bool)
        assert isinstance(cfg.get("is_remote"), bool)
        assert "param_map" in cfg
        if cfg["is_remote"]:  # remote backends must declare a credential env var
            assert cfg.get("api_env_var")


def test_registered_backends_are_in_ledger():
    """Every implemented backend should have a ledger record (no orphans)."""
    for bid in scribed.list_backends():
        assert bid in scribed.catalog, f"{bid} implemented but missing from ledger"


# ---------------------------------------------------------------------------
# Parameter translation
# ---------------------------------------------------------------------------


def test_kwargs_translator_rename_default_coerce():
    from scribed.translation import make_kwargs_translator

    translate = make_kwargs_translator(
        {
            "language": {"native_name": "language_code"},
            "model": {"native_name": "model_id", "default": "scribe_v1"},
            "diarize": {"native_name": "diarize", "coerce": bool},
        }
    )
    out = translate(language="en", diarize=1)
    assert out == {"language_code": "en", "diarize": True, "model_id": "scribe_v1"}


def test_kwargs_translator_unsupported_warns_and_drops():
    from scribed.translation import make_kwargs_translator

    translate = make_kwargs_translator({"language": {"native_name": "language"}})
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        out = translate(language="en", bogus=123)
    assert out == {"language": "en"}
    assert any("bogus" in str(x.message) for x in w)


def test_kwargs_translator_none_means_unsupported():
    from scribed.translation import make_kwargs_translator

    translate = make_kwargs_translator(
        {"language": {"native_name": "language"}, "diarize": None}
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = translate(language="en", diarize=True)
    assert out == {"language": "en"}


# ---------------------------------------------------------------------------
# Result-building helpers (make_segment / make_word)
# ---------------------------------------------------------------------------


def test_make_segment_confidence_normalization():
    s = scribed.make_segment("hi", start=0, end=1, confidence=87, conf_scale=100)
    assert abs(s.confidence - 0.87) < 1e-9
    assert s.span == TimeSpan(0, 1000)  # seconds surface -> millisecond TimeSpan
    assert (s.start, s.end) == (0.0, 1.0)  # float-second convenience accessors
    w = scribed.make_word("hi", start=0, end=1, confidence=1.5)  # clamped
    assert w.confidence == 1.0


# ---------------------------------------------------------------------------
# Input classification (no numpy/soundfile needed for these kinds)
# ---------------------------------------------------------------------------


def test_classify_input():
    from scribed.util import classify_input

    assert classify_input(b"\x00\x01") == "bytes"
    assert classify_input("http://example.com/a.mp3") == "url"
    assert classify_input("/tmp/a.wav") == "path"
    import io

    assert classify_input(io.BytesIO(b"x")) == "file"
    with pytest.raises(TypeError):
        classify_input(12345)


# ---------------------------------------------------------------------------
# Install / status reporting (no network)
# ---------------------------------------------------------------------------


def test_requirements_structure():
    req = scribed.requirements("deepgram")
    assert req.backend_id == "deepgram"
    assert req.is_remote is True
    assert "scribed[deepgram]" in req.pip_command
    assert isinstance(req.instructions(), str)


def test_requirements_local_system_dep():
    req = scribed.requirements("whisper")
    # openai-whisper needs ffmpeg surfaced as a system dep (unless already usable).
    assert req.is_local is True
    assert any("ffmpeg" in s for s in req.system) or req.available


def test_doctor_shape():
    rep = scribed.doctor()
    assert set(rep) == {"available", "missing"}
    assert isinstance(rep["available"], list)
    assert isinstance(rep["missing"], dict)


def test_check_returns_bool():
    assert isinstance(scribed.check("vosk"), bool)
    assert scribed.check("definitely-not-a-backend") is False


def test_status_table_renders():
    table = scribed.status_table(run_tests=False)
    assert "Name" in table and "Impl" in table and "Diar" in table
    assert "faster-whisper" in table


def test_backend_ids_levels():
    impl = scribed.backend_ids("implemented")
    assert EXPECTED_BACKENDS <= set(impl)
    assert set(impl) <= set(scribed.backend_ids("all"))


# ---------------------------------------------------------------------------
# Services layer
# ---------------------------------------------------------------------------


def test_services_access():
    assert "deepgram" in scribed.services
    handle = scribed.services["deepgram"]
    assert handle.name == "deepgram"
    assert handle.info["id"] == "deepgram"
    assert scribed.services.deepgram.name == "deepgram"
    with pytest.raises(AttributeError):
        scribed.services.nonexistent_backend  # noqa: B018
