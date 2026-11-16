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


def test_textgrid_round_trip_with_words_and_speakers():
    from scribed.base import Segment, TimeSpan, Word

    def w(text, a, b):
        return Word(text, TimeSpan.from_seconds(a, b))

    t = Transcript.from_segments(
        [
            Segment(
                "Hi there.",
                span=TimeSpan.from_seconds(0.5, 1.5),
                speaker="carl",
                words=(w("Hi", 0.5, 0.9), w("there.", 1.0, 1.5)),
            ),
            Segment(
                'Say "no".',
                span=TimeSpan.from_seconds(1.5, 3.0),
                speaker="ana",
                words=(w("Say", 1.6, 2.0), w('"no".', 2.1, 3.0)),
            ),
        ]
    )
    grid = t.as_textgrid()
    assert 'name = "utterances"' in grid and 'name = "words"' in grid
    back = Transcript.parse(grid)
    assert [(s.speaker, s.text) for s in back] == [
        ("carl", "Hi there."),
        ("ana", 'Say "no".'),
    ]
    assert [x.text for x in back.words] == ["Hi", "there.", "Say", '"no".']
    assert "words" not in t.as_textgrid(words=False).split('name = "utterances"')[1]


def test_textgrid_tiers_are_the_one_home_for_the_format():
    from scribed.textgrid import read_tiers, write_tiers

    tiers = {"take": [(0.5, 1.2, 'say "hi"')], 'odd "name"': [(0, 1, "x")]}
    back = read_tiers(write_tiers(tiers, xmax=2.0))
    assert back["take"] == [(0.0, 0.5, ""), (0.5, 1.2, 'say "hi"'), (1.2, 2.0, "")]
    assert 'odd "name"' in back
    with pytest.raises(ValueError, match="overlaps"):
        write_tiers({"t": [(0, 1, "a"), (0.5, 2, "b")]}, xmax=2)
    with pytest.raises(ValueError, match="outside"):
        write_tiers({"t": [(0, 3, "a")]}, xmax=2)


def test_textgrid_overlapping_speakers_are_trimmed_not_rejected():
    from scribed.base import Segment, TimeSpan

    t = Transcript.from_segments(
        [
            Segment("a", span=TimeSpan.from_seconds(0, 2), speaker="x"),
            Segment("b", span=TimeSpan.from_seconds(1, 3), speaker="y"),
        ]
    )
    back = Transcript.parse(t.as_textgrid())
    assert [(s.speaker, s.start, s.end) for s in back] == [
        ("x", 0.0, 1.0),
        ("y", 1.0, 3.0),
    ]
