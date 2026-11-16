"""Read a transcript back into a :class:`~scribed.base.Transcript`.

scribed writes subtitles (``Transcript.srt`` / ``.vtt``); this module is the
reading direction, for a transcript that already exists: an SRT or WebVTT from a
recording session, a Praat TextGrid from an aligner, a word-timed JSON from an
earlier ASR run, or plain ``speaker: text`` lines (untimed)::

    t = scribed.read_transcript("take1.srt")      # or Transcript.parse(...)
    for seg in t:
        print(seg.speaker, seg.start, seg.end, seg.words)

The format is detected by file suffix, then by content; pass ``fmt`` to force one
of :data:`FORMATS`. A parsed transcript carries ``backend="file:<fmt>"`` so
downstream code can tell it from an ASR result. No dependencies.

>>> t = read_transcript("1\\n00:00:01,000 --> 00:00:02,500\\n[carl] Hello there.\\n")
>>> [(s.speaker, s.text, s.start, s.end) for s in t], t.backend
([('carl', 'Hello there.', 1.0, 2.5)], 'file:srt')
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from scribed.base import Segment, TimeSpan, Transcript, Word
from scribed.textgrid import read_tiers

__all__ = ["FORMATS", "detect_format", "parse_timestamp", "read_transcript"]

#: The transcript formats read here, in detection order.
FORMATS: Tuple[str, ...] = ("vtt", "textgrid", "json", "srt", "plain")

#: File suffixes that name a format outright.
_SUFFIX_FORMATS = {
    ".srt": "srt",
    ".vtt": "vtt",
    ".webvtt": "vtt",
    ".textgrid": "textgrid",
    ".json": "json",
    ".txt": "plain",
    ".md": "plain",
}

#: Longest string tried as a filesystem path before it is taken as the text itself.
_MAX_PATH_LEN = 4096
#: Leading slice of a TextGrid searched for its tier markers.
_TEXTGRID_SNIFF_LEN = 4000
#: TextGrid labels that mark silence/non-words, not speech.
_TEXTGRID_NON_WORDS = ("sil", "sp", "<unk>")

_TIME_RE = re.compile(
    r"^\s*(?:(?P<h>\d+):)?(?P<m>\d{1,2}):(?P<s>\d{1,2})(?:[.,](?P<ms>\d{1,3}))?\s*$"
)
_SECONDS_RE = re.compile(r"^\s*(?P<s>\d+(?:\.\d*)?|\.\d+)\s*s?\s*$")
_ARROW_RE = re.compile(r"^\s*(?P<a>[^\s]+)\s+-->\s+(?P<b>[^\s]+)(?P<rest>.*)$")
_SRT_CUE_RE = re.compile(
    r"\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}\s+-->\s+\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}"
)
#: ``speaker: text`` (a scene-script line) or ``[speaker] text`` (what ``as_srt`` writes).
_SPEAKER_RE = re.compile(r"^\s*(?P<speaker>[\w-]+)\s*:\s*(?P<text>.*)$")
_BRACKET_SPEAKER_RE = re.compile(r"^\s*\[(?P<speaker>[^\]]+)\]\s*(?P<text>.*)$")
_VTT_VOICE_RE = re.compile(r"<v(?:\.[^\s>]*)?\s+(?P<name>[^>]+)>")
_TAG_RE = re.compile(r"<[^>]+>")

# (text, start_s, end_s) — the intermediate word form every parser produces.
_WordT = Tuple[str, float, float]
# (text, start_s | None, end_s | None, speaker | None, words | None)
_Row = Tuple[
    str, Optional[float], Optional[float], Optional[str], Optional[Tuple[_WordT, ...]]
]


# --- public API -------------------------------------------------------------------


def detect_format(text: str, *, suffix: str = "") -> str:
    """Which of :data:`FORMATS` ``text`` is: by file suffix first, then by content.

    >>> detect_format("WEBVTT\\n\\n00:01.000 --> 00:02.000\\nhi")
    'vtt'
    >>> detect_format("1\\n00:00:01,000 --> 00:00:02,000\\nhi"), detect_format("hi there")
    ('srt', 'plain')
    >>> detect_format('{"segments": []}'), detect_format("", suffix=".TextGrid")
    ('json', 'textgrid')
    """
    fmt = _SUFFIX_FORMATS.get(suffix.lower())
    if fmt is not None:
        return fmt
    head = text.lstrip()
    if head.startswith("WEBVTT"):
        return "vtt"
    if (
        head.startswith('File type = "ooTextFile"')
        or '"IntervalTier"' in head[:_TEXTGRID_SNIFF_LEN]
    ):
        return "textgrid"
    if head[:1] in ("{", "["):
        return "json"
    if _SRT_CUE_RE.search(text):
        return "srt"
    return "plain"


def parse_timestamp(value: str) -> float:
    """``HH:MM:SS,mmm`` / ``MM:SS.mmm`` / plain seconds -> seconds.

    >>> parse_timestamp("00:01:02,500"), parse_timestamp("01:02.5"), parse_timestamp("7.25")
    (62.5, 62.5, 7.25)
    """
    m = _TIME_RE.match(value)
    if m:
        ms = (m.group("ms") or "0").ljust(3, "0")
        return (
            int(m.group("h") or 0) * 3600
            + int(m.group("m")) * 60
            + int(m.group("s"))
            + int(ms) / 1000.0
        )
    m = _SECONDS_RE.match(value)
    if m:
        return float(m.group("s"))
    raise ValueError(f"not a timestamp: {value!r}")


def read_transcript(
    source: Union[str, Path], *, fmt: Optional[str] = None
) -> Transcript:
    """Read ``source`` (a path to a transcript file, or the transcript text itself).

    ``fmt`` (one of :data:`FORMATS`) overrides detection. The result's ``backend``
    is ``"file:<fmt>"``.

    >>> t = read_transcript("carl: Hello.\\nned: Hi.")
    >>> t.speakers, t.backend, t.segments[0].span
    (['carl', 'ned'], 'file:plain', None)
    """
    text, suffix = _load(source)
    fmt = (fmt or detect_format(text, suffix=suffix)).lower()
    try:
        parse = _PARSERS[fmt]
    except KeyError:
        raise ValueError(
            f"unknown transcript format {fmt!r}; known: {FORMATS}"
        ) from None
    segments = [_to_segment(row) for row in parse(text)]
    duration = max(
        (s.span.end_ms for s in segments if s.span is not None), default=None
    )
    return Transcript.from_segments(
        segments,
        backend=f"file:{fmt}",
        duration=None if duration is None else duration / 1000.0,
    )


# --- helpers ----------------------------------------------------------------------


def _load(source: Union[str, Path]) -> Tuple[str, str]:
    """``(text, suffix)``: read ``source`` if it names a file, else it is the text."""
    path = (
        Path(source)
        if isinstance(source, (str, Path)) and len(str(source)) < _MAX_PATH_LEN
        else None
    )
    try:
        is_file = path is not None and path.is_file()
    except OSError:  # e.g. text with a NUL or an over-long component
        is_file = False
    if is_file:
        return path.read_text(encoding="utf-8-sig"), path.suffix
    return str(source), ""


def _to_segment(row: _Row) -> Segment:
    text, start, end, speaker, words = row
    span = (
        TimeSpan.from_seconds(start, end)
        if start is not None and end is not None
        else None
    )
    return Segment(
        text=text,
        span=span,
        speaker=speaker,
        words=tuple(Word(t, TimeSpan.from_seconds(a, b)) for t, a, b in (words or ())),
    )


def _speaker_and_text(text: str) -> Tuple[Optional[str], str]:
    """``'carl: Hi'`` / ``'[carl] Hi'`` -> ``('carl', 'Hi')``; no prefix keeps ``None``."""
    for pattern in (_BRACKET_SPEAKER_RE, _SPEAKER_RE):
        m = pattern.match(text)
        if m and m.group("text").strip():
            return m.group("speaker").strip(), m.group("text").strip()
    return None, text.strip()


def _cue_blocks(text: str) -> Iterable[List[str]]:
    block: List[str] = []
    for line in text.splitlines():
        if line.strip():
            block.append(line.rstrip("\r"))
        elif block:
            yield block
            block = []
    if block:
        yield block


def _timed_cue(lines: List[str]) -> Optional[_Row]:
    """A cue block (optional id line, the time line, the text) -> a row."""
    for i, line in enumerate(lines[:2]):
        arrow = _ARROW_RE.match(line)
        if arrow:
            start, end = (
                parse_timestamp(arrow.group("a")),
                parse_timestamp(arrow.group("b")),
            )
            body = " ".join(part.strip() for part in lines[i + 1 :]).strip()
            speaker = None
            voice = _VTT_VOICE_RE.search(body)
            if voice:
                speaker = voice.group("name").strip()
            body = _TAG_RE.sub("", body).strip()
            if speaker is None:
                speaker, body = _speaker_and_text(body)
            return (body, start, end, speaker, None)
    return None


# --- per-format parsers (text -> rows) ---------------------------------------------


def _parse_srt(text: str) -> List[_Row]:
    rows = (_timed_cue(block) for block in _cue_blocks(text))
    return [r for r in rows if r is not None and r[0]]


def _unescape_vtt_row(row: _Row) -> _Row:
    """WebVTT cue text and voice names are HTML-escaped (``&amp;``, ``&lt;``)."""
    body, start, end, speaker, words = row
    return (html.unescape(body), start, end, speaker and html.unescape(speaker), words)


def _parse_vtt(text: str) -> List[_Row]:
    rows = (
        _timed_cue(block)
        for block in _cue_blocks(text)
        if not block[0].startswith(("WEBVTT", "NOTE", "STYLE", "REGION"))
    )
    return [_unescape_vtt_row(r) for r in rows if r is not None and r[0]]


def _parse_plain(text: str) -> List[_Row]:
    out: List[_Row] = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        speaker, body = _speaker_and_text(line)
        if body:
            out.append((body, None, None, speaker, None))
    return out


def _number(obj: Mapping[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        if key in obj and obj[key] is not None:
            value = float(obj[key])
            return value / 1000.0 if key.endswith("_ms") else value
    return None


def _word_from(item: Any) -> Optional[_WordT]:
    if isinstance(item, Mapping):
        text = item.get("text", item.get("word"))
        start, end = _number(item, "start", "start_ms"), _number(item, "end", "end_ms")
    elif isinstance(item, Sequence) and len(item) == 3 and not isinstance(item, str):
        text, start, end = item[0], float(item[1]), float(item[2])
    else:
        return None
    if text is None or start is None or end is None:
        return None
    return (str(text), float(start), float(end))


def _parse_json(text: str) -> List[_Row]:
    """Accepted: ``{"segments": [...]}`` or a list of segments, each ``{"text",
    "start", "end", "speaker", "words": [{"text"|"word", "start", "end"}, ...]}``
    (``start_ms``/``end_ms`` too; a word may be ``[text, start, end]``); or a bare
    list of words, read as one segment. A *top-level list* of ``{"text", "start",
    "end"}`` without any ``words`` is ambiguous and is read as words; wrap segments
    in ``{"segments": [...]}`` to keep them apart."""
    obj = json.loads(text)
    maybe_words = False  # could ``items`` be a bare list of words (one line)?
    if isinstance(obj, Mapping):
        items = obj.get("segments")  # entries here are segments, never words
        if items is None:
            items = obj.get("words")
            if items is None:
                raise ValueError(
                    "a transcript JSON needs a 'segments' (or 'words') list"
                )
            items = [{"words": items}]
    else:
        items = list(obj)
        # An entry with its own "words" is a segment; text/start/end alone is ambiguous
        # (a word or an untimed-words segment), and reads as a word.
        maybe_words = not any(isinstance(it, Mapping) and "words" in it for it in items)
    if maybe_words and items and all(_word_from(it) is not None for it in items):
        items = [{"words": items}]
    out: List[_Row] = []
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError(f"a transcript segment must be an object, got {item!r}")
        raw_words = item.get("words") or ()
        words = tuple(w for w in (_word_from(x) for x in raw_words) if w)
        body = item.get("text")
        if not body:  # absent or empty: rebuild it from the words (a word entry too)
            if not words and _word_from(item):
                words = (_word_from(item),)
            body = None
        if body is None:
            body = " ".join(w[0] for w in words)
        start, end = _number(item, "start", "start_ms"), _number(item, "end", "end_ms")
        if words:
            start = words[0][1] if start is None else start
            end = words[-1][2] if end is None else end
        speaker = item.get("speaker") or next(
            (
                w.get("speaker")
                for w in raw_words
                if isinstance(w, Mapping) and w.get("speaker")
            ),
            None,
        )
        if speaker:
            speaker, body = str(speaker), str(body).strip()
        else:
            speaker, body = _speaker_and_text(str(body))
        if body:
            out.append((body, start, end, speaker, words or None))
    return out


#: Tier names whose intervals are the LINES (one segment each), by preference.
_TG_LINE_TIERS = (
    "utterances",
    "utterance",
    "lines",
    "line",
    "sentences",
    "sentence",
    "segments",
)
#: Tier names whose intervals are the WORDS, by preference.
_TG_WORD_TIERS = ("words", "word", "ortho", "orthography")


def _parse_textgrid(text: str) -> List[_Row]:
    """Words come from a tier named ``words`` (else the first interval tier); a tier
    named ``utterances``/``lines``/``sentences`` gives one segment per non-empty
    interval, with the words inside it; without one, the whole grid is one segment."""
    tiers = read_tiers(text)
    if not tiers:
        raise ValueError("no IntervalTier found in the TextGrid")
    lowered = {name.lower(): name for name in tiers}
    word_tier = next(
        (lowered[n] for n in _TG_WORD_TIERS if n in lowered), next(iter(tiers))
    )
    words = [
        (t, a, b) for a, b, t in tiers[word_tier] if t and t not in _TEXTGRID_NON_WORDS
    ]
    line_tier = next((lowered[n] for n in _TG_LINE_TIERS if n in lowered), None)
    if line_tier is None:
        if not words:
            return []
        return [
            (
                " ".join(w[0] for w in words),
                words[0][1],
                words[-1][2],
                None,
                tuple(words),
            )
        ]
    out: List[_Row] = []
    for a, b, t in tiers[line_tier]:
        if not t:
            continue
        inside = tuple(w for w in words if w[1] >= a - 1e-6 and w[2] <= b + 1e-6)
        speaker, body = _speaker_and_text(t)
        out.append((body, a, b, speaker, inside or None))
    return out


_PARSERS = {
    "srt": _parse_srt,
    "vtt": _parse_vtt,
    "json": _parse_json,
    "textgrid": _parse_textgrid,
    "plain": _parse_plain,
}
