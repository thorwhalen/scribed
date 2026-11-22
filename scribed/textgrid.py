"""Praat TextGrid interval tiers, in and out: the one home for the format.

A TextGrid holds named *interval tiers*: ``{name: [(start, end, label), ...]}`` in
seconds. :func:`read_tiers` reads them from the long or the short text form (point
tiers are skipped); :func:`write_tiers` writes the long form, padding the gaps with
empty intervals (Praat requires a tier to cover its whole span); :func:`trim_overlaps`
makes intervals that overlap (speakers talking over each other) writable. What to *do* with tiers (which
one holds the words, speaker prefixes, phone tiers) is the caller's business:
:mod:`scribed.readers` turns them into a transcript, and ``Transcript.as_textgrid``
writes one.

The tier *conventions* the fleet's readers share live here too, so they cannot drift
apart: which tier names hold lines, words and phones (:data:`LINE_TIERS`,
:data:`WORD_TIERS`, :data:`PHONE_TIERS`), MFA's ``"<speaker> - <tier>"`` names
(:func:`speaker_and_tier`), the tier that names each line's speaker
(:data:`SPEAKER_TIERS`), and which labels are speech rather than silence or a marker
(:func:`is_speech`).

>>> grid = write_tiers({"take": [(0.5, 1.2, 'say "hi"')]}, xmax=2.0)
>>> read_tiers(grid)
{'take': [(0.0, 0.5, ''), (0.5, 1.2, 'say "hi"'), (1.2, 2.0, '')]}
"""

from __future__ import annotations

import re
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

__all__ = [
    "read_tiers",
    "write_tiers",
    "trim_overlaps",
    "is_speech",
    "speaker_and_tier",
    "tier_named",
    "Interval",
    "Tiers",
    "TIME_DECIMALS",
    "LINE_TIERS",
    "WORD_TIERS",
    "PHONE_TIERS",
    "SPEAKER_TIERS",
    "KNOWN_TIERS",
    "SPEAKER_SEP",
    "SILENCE_LABELS",
    "MARKER_BRACKETS",
]

#: ``(start, end, label)``, in seconds.
Interval = Tuple[float, float, str]
#: ``{tier name: intervals}``.
Tiers = Dict[str, List[Interval]]

#: Decimal places written for a time (fixed-point: the reader takes no exponent).
TIME_DECIMALS = 6

#: Tier names whose intervals are the LINES (one segment each), by preference.
LINE_TIERS: Tuple[str, ...] = (
    "utterances",
    "utterance",
    "lines",
    "line",
    "sentences",
    "sentence",
    "segments",
)
#: Tier names whose intervals are the WORDS, by preference.
WORD_TIERS: Tuple[str, ...] = ("words", "word", "ortho", "orthography")
#: Tier names a forced aligner gives its phones (MFA: ``phones``; WebMAUS: ``MAU``).
PHONE_TIERS: Tuple[str, ...] = ("phones", "phone", "phonemes", "phoneme", "mau")
#: Tier names whose intervals name the speaker of the line they cover (empty: none).
#: Written beside a lines tier when a ``speaker: text`` prefix would be ambiguous.
SPEAKER_TIERS: Tuple[str, ...] = ("speakers", "speaker")
#: Every tier name a ``"<speaker> - <tier>"`` name may end with (lower case), so a
#: tier called ``"notes - draft"`` is not a speaker's.
KNOWN_TIERS = frozenset(LINE_TIERS + WORD_TIERS + PHONE_TIERS)
#: MFA's separator between a speaker and its tier's name (``"carl - words"``).
SPEAKER_SEP = " - "
#: Labels that are silence or an unknown word, not speech (compared lower case):
#: MFA's ``sil``, ``sp`` and ``spn``, Gentle's ``oov``, and the empty label.
SILENCE_LABELS = frozenset({"sil", "sp", "spn", "oov", ""})
#: A label wrapped in one of these pairs is a marker, not speech (``<unk>``,
#: WebMAUS's ``<p:>``, ``[noise]``, ``+breath+``).
MARKER_BRACKETS: Tuple[Tuple[str, str], ...] = (("<", ">"), ("[", "]"), ("+", "+"))

_TIER_RE = re.compile(
    r'class\s*=\s*"IntervalTier"\s*\n\s*name\s*=\s*"(?P<name>(?:[^"]|"")*)"', re.S
)
_INTERVAL_RE = re.compile(
    r'xmin\s*=\s*(?P<a>[-+\d.eE]+)\s*\n\s*xmax\s*=\s*(?P<b>[-+\d.eE]+)\s*\n\s*text\s*=\s*"(?P<t>(?:[^"]|"")*)"'
)
_SHORT_TIER_RE = re.compile(
    r'"(?P<kind>IntervalTier|TextTier)"\s*\n\s*"(?P<name>(?:[^"]|"")*)"\s*\n'
)
_SHORT_INTERVAL_RE = re.compile(
    r'(?P<a>\d+(?:\.\d+)?)\s*\n\s*(?P<b>\d+(?:\.\d+)?)\s*\n\s*"(?P<t>(?:[^"]|"")*)"'
)


def read_tiers(text: str) -> Tiers:
    """``{tier name: [(start, end, label), ...]}`` for every interval tier (long or short form).

    Labels are stripped; a doubled ``""`` is a quote.

    >>> read_tiers(write_tiers({"a": [(0, 1, "x")]}, xmax=1))
    {'a': [(0.0, 1.0, 'x')]}
    """
    tiers: Tiers = {}
    long_form = list(_TIER_RE.finditer(text))
    heads = long_form if long_form else list(_SHORT_TIER_RE.finditer(text))
    kinds = [h.groupdict().get("kind", "IntervalTier") for h in heads]
    interval_re = _INTERVAL_RE if long_form else _SHORT_INTERVAL_RE
    for i, head in enumerate(heads):
        if (
            kinds[i] != "IntervalTier"
        ):  # a point tier: not intervals, but it ends the chunk
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        intervals = [
            (
                float(m.group("a")),
                float(m.group("b")),
                m.group("t").replace('""', '"').strip(),
            )
            for m in interval_re.finditer(text[head.end() : end])
        ]
        tiers[head.group("name").replace('""', '"')] = intervals
    return tiers


def write_tiers(tiers: Mapping[str, Sequence[Interval]], *, xmax: float) -> str:
    """A long-form TextGrid of interval ``tiers`` spanning ``0..xmax``.

    What :func:`read_tiers` reads back, and what a forced aligner takes as a
    transcript of timed lines. Gaps between intervals are filled with empty ones;
    a ``"`` in a label or tier name is doubled. Times are rounded to
    :data:`TIME_DECIMALS` places before they are checked. Nothing is clamped: an
    interval outside ``0..xmax``, empty, or overlapping another is a ``ValueError``
    (use :func:`trim_overlaps` first where overlap is expected). The reader strips
    labels, so a label's surrounding whitespace does not survive a round trip.

    >>> write_tiers({"take": [(0.5, 1.2, "a"), (1.0, 1.5, "b")]}, xmax=2.0)
    Traceback (most recent call last):
      ...
    ValueError: tier 'take': interval (1.0, 1.5, 'b') overlaps the one before, which ends at 1.2
    """

    def quoted(text: str) -> str:
        return text.replace('"', '""')

    xmax = round(xmax, TIME_DECIMALS)

    def num(x: float) -> str:
        return f"{x:.{TIME_DECIMALS}f}".rstrip("0").rstrip(".") or "0"

    def tiled(name: str, intervals: Sequence[Interval]) -> List[Interval]:
        out, t = [], 0.0
        rounded = (
            (round(a, TIME_DECIMALS), round(b, TIME_DECIMALS), label)
            for a, b, label in intervals
        )
        for a, b, label in sorted(rounded):
            if not 0.0 <= a < b <= xmax:
                raise ValueError(
                    f"tier {name!r}: interval {(a, b, label)!r} is empty or outside 0..{xmax}"
                )
            if a < t:
                raise ValueError(
                    f"tier {name!r}: interval {(a, b, label)!r} overlaps the one "
                    f"before, which ends at {t}"
                )
            if a > t:
                out.append((t, a, ""))
            out.append((a, b, label))
            t = b
        return out + ([(t, xmax, "")] if t < xmax else [])

    lines = [
        'File type = "ooTextFile"',
        'Object class = "TextGrid"',
        "",
        "xmin = 0",
        f"xmax = {num(xmax)}",
        "tiers? <exists>",
        f"size = {len(tiers)}",
        "item []:",
    ]
    for i, (name, intervals) in enumerate(tiers.items(), start=1):
        cells = tiled(name, intervals)
        lines += [
            f"    item [{i}]:",
            '        class = "IntervalTier"',
            f'        name = "{quoted(name)}"',
            "        xmin = 0",
            f"        xmax = {num(xmax)}",
            f"        intervals: size = {len(cells)}",
        ]
        for j, (a, b, label) in enumerate(cells, start=1):
            lines += [
                f"        intervals [{j}]:",
                f"            xmin = {num(a)}",
                f"            xmax = {num(b)}",
                f'            text = "{quoted(label)}"',
            ]
    return "\n".join(lines) + "\n"


def trim_overlaps(intervals: Sequence[Interval]) -> List[Interval]:
    """``intervals`` sorted, each ending no later than the next begins.

    For speakers talking over each other, which a single tier cannot hold. An
    interval that is trimmed to nothing (it starts where another starts) is
    dropped (of two intervals with the same start, the later-sorting one is kept).

    >>> trim_overlaps([(1, 3, "b"), (0, 2, "a")])
    [(0, 1, 'a'), (1, 3, 'b')]
    """
    ordered = sorted(intervals)
    out: List[Interval] = []
    for i, (start, end, label) in enumerate(ordered):
        if i + 1 < len(ordered):
            end = min(end, ordered[i + 1][0])
        if end > start:
            out.append((start, end, label))
    return out


def is_speech(label: str) -> bool:
    """Whether an interval label is speech, not silence (:data:`SILENCE_LABELS`, any
    case) or a marker (wrapped in :data:`MARKER_BRACKETS`).

    >>> [is_speech(x) for x in ("hello", "SIL", "spn", "<p:>", "+breath+", "[noise]", "AH0")]
    [True, False, False, False, False, False, True]
    """
    text = label.strip()
    if text.lower() in SILENCE_LABELS:
        return False
    return not any(
        len(text) >= 2 and text.startswith(a) and text.endswith(b)
        for a, b in MARKER_BRACKETS
    )


def speaker_and_tier(name: str) -> Tuple[Optional[str], str]:
    """MFA's ``"<speaker> - words"`` -> ``("<speaker>", "words")``. Only a known tier
    name after the separator (:data:`KNOWN_TIERS`, any case) makes a speaker; any
    other name -> ``(None, name)``.

    >>> speaker_and_tier("carl - words"), speaker_and_tier("notes - draft")
    (('carl', 'words'), (None, 'notes - draft'))
    """
    speaker, sep, bare = name.rpartition(SPEAKER_SEP)
    if sep and speaker.strip() and bare.strip().lower() in KNOWN_TIERS:
        return speaker.strip(), bare.strip()
    return None, name


def tier_named(tiers: Mapping[str, object], names: Sequence[str]) -> Optional[str]:
    """The name of the tier in ``tiers`` called one of ``names`` (any case, a
    speaker's prefix aside), by the order of ``names``; None if there is none.

    >>> tier_named({"Carl - Words": [], "notes": []}, WORD_TIERS)
    'Carl - Words'
    """
    bare = {}
    for name in tiers:
        bare.setdefault(speaker_and_tier(name)[1].lower(), name)
    return next((bare[n] for n in names if n in bare), None)
