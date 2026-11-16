"""Praat TextGrid interval tiers, in and out: the one home for the format.

A TextGrid holds named *interval tiers*: ``{name: [(start, end, label), ...]}`` in
seconds. :func:`read_tiers` reads them from the long or the short text form;
:func:`write_tiers` writes the long form, padding the gaps with empty intervals
(Praat requires a tier to cover its whole span). What to *do* with tiers (which
one holds the words, speaker prefixes, phone tiers) is the caller's business:
:mod:`scribed.readers` turns them into a transcript, and ``Transcript.as_textgrid``
writes one.

>>> grid = write_tiers({"take": [(0.5, 1.2, 'say "hi"')]}, xmax=2.0)
>>> read_tiers(grid)
{'take': [(0.0, 0.5, ''), (0.5, 1.2, 'say "hi"'), (1.2, 2.0, '')]}
"""

from __future__ import annotations

import re
from typing import Dict, List, Mapping, Sequence, Tuple

__all__ = ["read_tiers", "write_tiers", "Tiers"]

#: ``(start, end, label)``, in seconds.
Interval = Tuple[float, float, str]
#: ``{tier name: intervals}``.
Tiers = Dict[str, List[Interval]]

#: Decimal places written for a time (fixed-point: the reader takes no exponent).
TIME_DECIMALS = 6

_TIER_RE = re.compile(
    r'class\s*=\s*"IntervalTier"\s*\n\s*name\s*=\s*"(?P<name>(?:[^"]|"")*)"', re.S
)
_INTERVAL_RE = re.compile(
    r'xmin\s*=\s*(?P<a>[\d.]+)\s*\n\s*xmax\s*=\s*(?P<b>[\d.]+)\s*\n\s*text\s*=\s*"(?P<t>(?:[^"]|"")*)"'
)
_SHORT_TIER_RE = re.compile(r'"IntervalTier"\s*\n\s*"(?P<name>(?:[^"]|"")*)"\s*\n')
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
    interval_re = _INTERVAL_RE if long_form else _SHORT_INTERVAL_RE
    for i, head in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        intervals = [
            (
                float(m.group("a")),
                float(m.group("b")),
                m.group("t").replace('""', '"').strip(),
            )
            for m in interval_re.finditer(text[head.end() : end])
        ]
        if not long_form and len(intervals) > 1 and intervals[0][2] == "":
            # the short form's tier header (xmin/xmax) is matched as a first interval
            intervals = intervals[1:]
        tiers[head.group("name").replace('""', '"')] = intervals
    return tiers


def write_tiers(tiers: Mapping[str, Sequence[Interval]], *, xmax: float) -> str:
    """A long-form TextGrid of interval ``tiers`` spanning ``0..xmax``.

    What :func:`read_tiers` reads back, and what a forced aligner takes as a
    transcript of timed lines. Gaps between intervals are filled with empty ones;
    a ``"`` in a label or tier name is doubled. Nothing is clamped: an interval
    outside ``0..xmax``, empty, or overlapping another is a ``ValueError``.

    >>> write_tiers({"take": [(0.5, 1.2, "a"), (1.0, 1.5, "b")]}, xmax=2.0)
    Traceback (most recent call last):
      ...
    ValueError: tier 'take': interval (1.0, 1.5, 'b') overlaps the one before, which ends at 1.2
    """

    def quoted(text: str) -> str:
        return text.replace('"', '""')

    def num(x: float) -> str:
        return f"{x:.{TIME_DECIMALS}f}".rstrip("0").rstrip(".") or "0"

    def tiled(name: str, intervals: Sequence[Interval]) -> List[Interval]:
        out, t = [], 0.0
        for a, b, label in sorted(intervals):
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
