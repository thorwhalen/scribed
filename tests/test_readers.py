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


SHORT_GRID = """File type = "ooTextFile"
Object class = "TextGrid"

0
2
<exists>
2
"IntervalTier"
"words"
0
2
3
0
0.5
""
0.5
1
"hi"
1
2
""
"TextTier"
"p"
0
2
1
1.0
"x"
"""


def test_short_form_keeps_leading_silence_and_skips_point_tiers():
    from scribed.textgrid import read_tiers

    assert read_tiers(SHORT_GRID) == {
        "words": [(0.0, 0.5, ""), (0.5, 1.0, "hi"), (1.0, 2.0, "")]
    }
    assert Transcript.parse(SHORT_GRID, fmt="textgrid").text == "hi"


def test_textgrid_exponent_times_are_read():
    from scribed.textgrid import read_tiers

    grid = (
        'class = "IntervalTier"\nname = "t"\nxmin = 0\nxmax = 1e0\nintervals: size = 1\n'
        'intervals [1]:\n  xmin = 0\n  xmax = 1e0\n  text = "a"\n'
    )
    assert read_tiers(grid) == {"t": [(0.0, 1.0, "a")]}


def test_lines_without_a_words_tier_do_not_invent_words():
    from scribed.base import Segment, TimeSpan

    t = Transcript.from_segments(
        [Segment("hello", span=TimeSpan.from_seconds(0, 1), speaker="a")]
    )
    for grid in (t.as_textgrid(), t.as_textgrid(words=False)):
        assert Transcript.parse(grid).words == []


def test_overlapping_speakers_with_words_get_per_speaker_tiers_not_a_flat_words_tier():
    from scribed.base import Segment, TimeSpan, Word

    def seg(text, a, b, who):
        word = Word(text, TimeSpan.from_seconds(a, b))
        return Segment(
            text, span=TimeSpan.from_seconds(a, b), speaker=who, words=(word,)
        )

    t = Transcript.from_segments([seg("a", 0, 2, "x"), seg("b", 1, 3, "y")])
    assert 'name = "words"' not in t.as_textgrid()
    same = Transcript.from_segments([seg("a", 0, 2, "x"), seg("b", 0, 3, "y")])
    assert [s.text for s in Transcript.parse(same.as_textgrid())] == ["a", "b"]
    # unspeakered overlap still has no word tier (nothing to key a tier on)
    anon = Transcript.from_segments([seg("a", 0, 2, None), seg("b", 1, 3, None)])
    assert "words" not in anon.as_textgrid().split('name = "utterances"')[1]


def test_write_tiers_checks_times_after_rounding():
    from scribed.textgrid import write_tiers

    grid = write_tiers({"t": [(0, 0.1 + 0.2, "a"), (0.3, 1, "b")]}, xmax=1)
    assert 'text = "b"' in grid


def test_textgrid_overlapping_speakers_get_one_tier_pair_each_and_keep_their_words():
    from scribed.base import Segment, TimeSpan, Word

    def seg(text, a, b, speaker):
        ws = text.split()
        step = (b - a) / len(ws)
        return Segment(
            text,
            span=TimeSpan.from_seconds(a, b),
            speaker=speaker,
            words=tuple(
                Word(w, TimeSpan.from_seconds(a + i * step, a + (i + 1) * step))
                for i, w in enumerate(ws)
            ),
        )

    t = Transcript.from_segments(
        [seg("one two", 0, 2, "x"), seg("three four", 1, 3, "y")]
    )
    grid = t.as_textgrid()
    assert 'name = "x - utterances"' in grid and 'name = "y - words"' in grid
    back = Transcript.parse(grid)
    assert [(s.speaker, s.text, s.start, s.end) for s in back] == [
        ("x", "one two", 0.0, 2.0),
        ("y", "three four", 1.0, 3.0),
    ]
    assert [w.text for s in back for w in s.words] == ["one", "two", "three", "four"]


# --------------------------------------------------------------- shared tier conventions (#32)


def test_silence_markers_and_unknown_words_are_not_words_in_any_case():
    from scribed.textgrid import write_tiers

    grid = write_tiers(
        {
            "utterances": [(0, 3, "hello there"), (3, 4, "SIL")],
            "words": [
                (0, 1, "hello"),
                (1, 1.5, "spn"),
                (1.5, 2, "<p:>"),
                (2, 2.5, "[noise]"),
                (2.5, 3, "there"),
                (3, 4, "SIL"),
            ],
        },
        xmax=4,
    )
    back = Transcript.parse(grid)
    assert [s.text for s in back] == ["hello there"]  # a "SIL" line is no line
    assert [w.text for w in back.words] == ["hello", "there"]


def test_mfa_speaker_tiers_with_other_known_names_are_read_per_speaker():
    from scribed.textgrid import write_tiers

    grid = write_tiers(
        {
            "carl - lines": [(0, 1, "hi")],
            "carl - word": [(0, 1, "hi")],
            "ana - utterances": [(1, 2, "yo")],
            "notes - draft": [(0, 2, "not a speaker")],
        },
        xmax=2,
    )
    back = Transcript.parse(grid)
    assert [(s.speaker, s.text) for s in back] == [("carl", "hi"), ("ana", "yo")]
    assert [w.text for w in back.words] == ["hi"]


def test_a_line_that_looks_like_a_speaker_prefix_round_trips_through_a_speakers_tier():
    from scribed.base import Segment, TimeSpan

    def seg(text, a, b, who=None):
        return Segment(text, span=TimeSpan.from_seconds(a, b), speaker=who)

    t = Transcript.from_segments(
        [
            seg("Note: this is not a speaker.", 0, 1),
            seg("Hi.", 1, 2, "carl"),
            seg("Hello.", 2, 3, "Dr Who"),  # a name with a space has no prefix form
        ]
    )
    grid = t.as_textgrid()
    assert 'name = "speakers"' in grid
    assert [(s.speaker, s.text) for s in Transcript.parse(grid)] == [
        (None, "Note: this is not a speaker."),
        ("carl", "Hi."),
        ("Dr Who", "Hello."),
    ]
    # nothing ambiguous: the prefix form, no speakers tier (the format did not change)
    plain = Transcript.from_segments([seg("Hi.", 0, 1, "carl"), seg("Yo.", 1, 2)])
    assert 'name = "speakers"' not in plain.as_textgrid()
    assert [(s.speaker, s.text) for s in Transcript.parse(plain.as_textgrid())] == [
        ("carl", "Hi."),
        (None, "Yo."),
    ]


def test_a_speakers_tier_is_never_taken_for_words():
    from scribed.textgrid import write_tiers

    grid = write_tiers(
        {"speakers": [(0, 1, "carl")], "utterances": [(0, 1, "a: b")]}, xmax=1
    )
    back = Transcript.parse(grid)
    assert [(s.speaker, s.text) for s in back] == [("carl", "a: b")]
    assert back.words == []
