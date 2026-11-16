"""Tests for reading transcripts back (SRT, WebVTT, TextGrid, JSON, plain)."""

import json

import pytest

import scribed
from scribed import Segment, TimeSpan, Transcript, Word

TEXTGRID_LONG = """File type = "ooTextFile"
Object class = "TextGrid"
xmin = 0
xmax = 2
tiers? <exists>
size = 2
item []:
    item [1]:
        class = "IntervalTier"
        name = "utterances"
        xmin = 0
        xmax = 2
        intervals: size = 1
        intervals [1]:
            xmin = 0.5
            xmax = 1.3
            text = "carl: hello there"
    item [2]:
        class = "IntervalTier"
        name = "words"
        xmin = 0
        xmax = 2
        intervals: size = 3
        intervals [1]:
            xmin = 0
            xmax = 0.5
            text = ""
        intervals [2]:
            xmin = 0.5
            xmax = 0.9
            text = "hello"
        intervals [3]:
            xmin = 0.9
            xmax = 1.3
            text = "there"
"""


def test_srt_round_trip():
    original = Transcript.from_segments(
        [
            Segment("Hello there.", TimeSpan(1000, 2500), speaker="carl"),
            Segment("Hi.", TimeSpan(3000, 3800)),
        ]
    )
    t = Transcript.parse(original.srt)
    assert t.backend == "file:srt"
    assert [(s.speaker, s.text, s.span) for s in t] == [
        (s.speaker, s.text, s.span) for s in original
    ]
    assert t.duration == 3.8


def test_vtt_round_trip_voice_tag():
    original = Transcript.from_segments(
        [Segment("Hello", TimeSpan(1000, 2000), speaker="Carl")]
    )
    t = Transcript.parse(original.vtt)
    assert t.backend == "file:vtt"
    assert (t.segments[0].speaker, t.segments[0].text) == ("Carl", "Hello")


def test_textgrid_long_form_words_inside_utterance():
    t = Transcript.parse(TEXTGRID_LONG)
    (seg,) = t.segments
    assert (seg.speaker, seg.text, seg.start, seg.end) == (
        "carl",
        "hello there",
        0.5,
        1.3,
    )
    assert seg.words == (
        Word("hello", TimeSpan(500, 900)),
        Word("there", TimeSpan(900, 1300)),
    )


def test_json_shapes():
    ms = {"segments": [{"text": "hi", "start_ms": 500, "end_ms": 900, "speaker": "a"}]}
    seg = Transcript.parse(json.dumps(ms)).segments[0]
    assert seg.span == TimeSpan(500, 900) and seg.speaker == "a"
    bare = json.dumps([{"word": "x", "start": 0, "end": 1}, ["y", 1, 2]])
    seg = Transcript.parse(bare).segments[0]
    assert seg.text == "x y" and seg.span == TimeSpan(0, 2000)


def test_plain_untimed_and_path(tmp_path):
    path = tmp_path / "scene.txt"
    path.write_text("carl: Hi.\n\nJust a line.\n")
    t = scribed.read_transcript(path)
    assert t.backend == "file:plain"
    assert [s.speaker for s in t] == ["carl", None]
    assert t.duration is None and t.segments[0].span is None


def test_detection_by_suffix_beats_content(tmp_path):
    path = tmp_path / "x.srt"
    path.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n")
    assert Transcript.parse(path).backend == "file:srt"


def test_unknown_format():
    with pytest.raises(ValueError, match="unknown transcript format"):
        Transcript.parse("hi", fmt="docx")


def test_json_segments_with_words_keep_their_segments_and_words():
    seg = lambda text, a, words: {  # noqa: E731
        "text": text,
        "start": a,
        "end": a + 2,
        "words": [
            {"text": w, "start": a + i, "end": a + i + 1} for i, w in enumerate(words)
        ],
    }
    doc = {"segments": [seg("hi there", 0, ["hi", "there"]), seg("you", 2, ["you"])]}
    for payload in (doc, doc["segments"]):  # object or bare list of segments
        t = Transcript.parse(json.dumps(payload))
        assert [s.text for s in t] == ["hi there", "you"]
        assert [[w.text for w in s.words] for s in t] == [["hi", "there"], ["you"]]


def test_json_segments_without_words_are_segments_not_words():
    doc = {
        "segments": [
            {"text": "a b", "start": 0, "end": 1},
            {"text": "c", "start": 1, "end": 2},
        ]
    }
    t = Transcript.parse(json.dumps(doc))
    assert [s.text for s in t] == ["a b", "c"] and t.words == []


def test_json_segments_of_bare_words_still_read_as_words():
    doc = {
        "segments": [
            {"word": "hi", "start": 0, "end": 0.5},
            {"word": "there", "start": 0.5, "end": 1},
        ]
    }
    t = Transcript.parse(json.dumps(doc))
    assert t.text == "hi there" and [w.text for w in t.words] == ["hi", "there"]


def test_json_segment_with_empty_text_is_rebuilt_from_its_words():
    seg = {
        "text": "",
        "start": 0,
        "end": 1,
        "words": [{"text": "hi", "start": 0, "end": 1}],
    }
    assert Transcript.parse(json.dumps({"segments": [seg]})).text == "hi"
