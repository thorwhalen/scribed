# scribed.textgrid

Praat TextGrid interval tiers, in and out: the one home for the format.

A TextGrid holds named *interval tiers*: `{name: [(start, end, label), ...]}` in
seconds. [`read_tiers()`](#scribed.textgrid.read_tiers) reads them from the long or the short text form (point
tiers are skipped); [`write_tiers()`](#scribed.textgrid.write_tiers) writes the long form, padding the gaps with
empty intervals (Praat requires a tier to cover its whole span); [`trim_overlaps()`](#scribed.textgrid.trim_overlaps)
makes intervals that overlap (speakers talking over each other) writable. What to *do* with tiers (which
one holds the words, speaker prefixes, phone tiers) is the caller’s business:
[`scribed.readers`](scribed.readers.html.md#module-scribed.readers) turns them into a transcript, and `Transcript.as_textgrid`
writes one.

The tier *conventions* the fleet’s readers share live here too, so they cannot drift
apart: which tier names hold lines, words and phones ([`LINE_TIERS`](#scribed.textgrid.LINE_TIERS),
[`WORD_TIERS`](#scribed.textgrid.WORD_TIERS), [`PHONE_TIERS`](#scribed.textgrid.PHONE_TIERS)), MFA’s `"<speaker> - <tier>"` names
([`speaker_and_tier()`](#scribed.textgrid.speaker_and_tier)), the tier that names each line’s speaker
([`SPEAKER_TIERS`](#scribed.textgrid.SPEAKER_TIERS)), and which labels are speech rather than silence or a marker
([`is_speech()`](#scribed.textgrid.is_speech)).

```pycon
>>> grid = write_tiers({"take": [(0.5, 1.2, 'say "hi"')]}, xmax=2.0)
>>> read_tiers(grid)
{'take': [(0.0, 0.5, ''), (0.5, 1.2, 'say "hi"'), (1.2, 2.0, '')]}
```

### Module Attributes

| [`Interval`](#scribed.textgrid.Interval)        | `(start, end, label)`, in seconds.                                                                                                              |
|------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|
| [`Tiers`](#scribed.textgrid.Tiers)           | `{tier name: intervals}`.                                                                                                                       |
| [`TIME_DECIMALS`](#scribed.textgrid.TIME_DECIMALS)   | the reader takes no exponent).                                                                                                                  |
| [`LINE_TIERS`](#scribed.textgrid.LINE_TIERS)      | Tier names whose intervals are the LINES (one segment each), by preference.                                                                     |
| [`WORD_TIERS`](#scribed.textgrid.WORD_TIERS)      | Tier names whose intervals are the WORDS, by preference.                                                                                        |
| [`PHONE_TIERS`](#scribed.textgrid.PHONE_TIERS)     | `MAU`).                                                                                                                                         |
| [`SPEAKER_TIERS`](#scribed.textgrid.SPEAKER_TIERS)   | none).                                                                                                                                          |
| [`KNOWN_TIERS`](#scribed.textgrid.KNOWN_TIERS)     | Every tier name a `"<speaker> - <tier>"` name may end with (lower case), so a tier called `"notes - draft"` is not a speaker's.                 |
| [`SPEAKER_SEP`](#scribed.textgrid.SPEAKER_SEP)     | MFA's separator between a speaker and its tier's name (`"carl - words"`).                                                                       |
| [`SILENCE_LABELS`](#scribed.textgrid.SILENCE_LABELS)  | Labels that are silence or an unknown word, not speech (compared lower case): MFA's `sil`, `sp` and `spn`, Gentle's `oov`, and the empty label. |
| [`MARKER_BRACKETS`](#scribed.textgrid.MARKER_BRACKETS) | A label wrapped in one of these pairs is a marker, not speech (`<unk>`, WebMAUS's `<p:>`, `[noise]`, `+breath+`).                               |

### Functions

| [`read_tiers`](#scribed.textgrid.read_tiers)(text)             | `{tier name: [(start, end, label), ...]}` for every interval tier (long or short form).                                                                                                                                 |
|-------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`write_tiers`](#scribed.textgrid.write_tiers)(tiers, \*, xmax) | A long-form TextGrid of interval `tiers` spanning `0..xmax`.                                                                                                                                                            |
| [`trim_overlaps`](#scribed.textgrid.trim_overlaps)(intervals)     | `intervals` sorted, each ending no later than the next begins.                                                                                                                                                          |
| [`is_speech`](#scribed.textgrid.is_speech)(label)             | Whether an interval label is speech, not silence ([`SILENCE_LABELS`](#scribed.textgrid.SILENCE_LABELS), any case) or a marker (wrapped in [`MARKER_BRACKETS`](#scribed.textgrid.MARKER_BRACKETS)). |
| [`speaker_and_tier`](#scribed.textgrid.speaker_and_tier)(name)       | MFA's `"<speaker> - words"` -> `("<speaker>", "words")`.                                                                                                                                                                |
| [`tier_named`](#scribed.textgrid.tier_named)(tiers, names)     | The name of the tier in `tiers` called one of `names` (any case, a speaker's prefix aside), by the order of `names`; None if there is none.                                                                             |

### scribed.textgrid.Interval

`(start, end, label)`, in seconds.

alias of `Tuple`[[`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### scribed.textgrid.KNOWN_TIERS *= frozenset({'line', 'lines', 'mau', 'ortho', 'orthography', 'phone', 'phoneme', 'phonemes', 'phones', 'segments', 'sentence', 'sentences', 'utterance', 'utterances', 'word', 'words'})*

Every tier name a `"<speaker> - <tier>"` name may end with (lower case), so a
tier called `"notes - draft"` is not a speaker’s.

### scribed.textgrid.LINE_TIERS *: [Tuple](https://docs.python.org/3/library/typing.html#typing.Tuple)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), ...]* *= ('utterances', 'utterance', 'lines', 'line', 'sentences', 'sentence', 'segments')*

Tier names whose intervals are the LINES (one segment each), by preference.

### scribed.textgrid.MARKER_BRACKETS *: [Tuple](https://docs.python.org/3/library/typing.html#typing.Tuple)[[Tuple](https://docs.python.org/3/library/typing.html#typing.Tuple)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [str](https://docs.python.org/3/builtins/stdtypes.html#str)], ...]* *= (('<', '>'), ('[', ']'), ('+', '+'))*

A label wrapped in one of these pairs is a marker, not speech (`<unk>`,
WebMAUS’s `<p:>`, `[noise]`, `+breath+`).

### scribed.textgrid.PHONE_TIERS *: [Tuple](https://docs.python.org/3/library/typing.html#typing.Tuple)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), ...]* *= ('phones', 'phone', 'phonemes', 'phoneme', 'mau')*

`MAU`).

* **Type:**
  Tier names a forced aligner gives its phones (MFA
* **Type:**
  `phones`; WebMAUS

### scribed.textgrid.SILENCE_LABELS *= frozenset({'', 'oov', 'sil', 'sp', 'spn'})*

Labels that are silence or an unknown word, not speech (compared lower case):
MFA’s `sil`, `sp` and `spn`, Gentle’s `oov`, and the empty label.

### scribed.textgrid.SPEAKER_SEP *= ' - '*

MFA’s separator between a speaker and its tier’s name (`"carl - words"`).

### scribed.textgrid.SPEAKER_TIERS *: [Tuple](https://docs.python.org/3/library/typing.html#typing.Tuple)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), ...]* *= ('speakers', 'speaker')*

none).
Written beside a lines tier when a `speaker: text` prefix would be ambiguous.

* **Type:**
  Tier names whose intervals name the speaker of the line they cover (empty

### scribed.textgrid.TIME_DECIMALS *= 6*

the reader takes no exponent).

* **Type:**
  Decimal places written for a time (fixed-point

### scribed.textgrid.Tiers

`{tier name: intervals}`.

alias of [`Dict`](https://docs.python.org/3/library/typing.html#typing.Dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`List`](https://docs.python.org/3/library/typing.html#typing.List)[`Tuple`[[`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]]

### scribed.textgrid.WORD_TIERS *: [Tuple](https://docs.python.org/3/library/typing.html#typing.Tuple)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), ...]* *= ('words', 'word', 'ortho', 'orthography')*

Tier names whose intervals are the WORDS, by preference.

### scribed.textgrid.is_speech(label)

Whether an interval label is speech, not silence ([`SILENCE_LABELS`](#scribed.textgrid.SILENCE_LABELS), any
case) or a marker (wrapped in [`MARKER_BRACKETS`](#scribed.textgrid.MARKER_BRACKETS)).

```pycon
>>> [is_speech(x) for x in ("hello", "SIL", "spn", "<p:>", "+breath+", "[noise]", "AH0")]
[True, False, False, False, False, False, True]
```

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### scribed.textgrid.read_tiers(text)

`{tier name: [(start, end, label), ...]}` for every interval tier (long or short form).

Labels are stripped; a doubled `""` is a quote.

```pycon
>>> read_tiers(write_tiers({"a": [(0, 1, "x")]}, xmax=1))
{'a': [(0.0, 1.0, 'x')]}
```

* **Return type:**
  [`Dict`](https://docs.python.org/3/library/typing.html#typing.Dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`List`](https://docs.python.org/3/library/typing.html#typing.List)[[`Tuple`](https://docs.python.org/3/library/typing.html#typing.Tuple)[[`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]]

### scribed.textgrid.speaker_and_tier(name)

MFA’s `"<speaker> - words"` -> `("<speaker>", "words")`. Only a known tier
name after the separator ([`KNOWN_TIERS`](#scribed.textgrid.KNOWN_TIERS), any case) makes a speaker; any
other name -> `(None, name)`.

```pycon
>>> speaker_and_tier("carl - words"), speaker_and_tier("notes - draft")
(('carl', 'words'), (None, 'notes - draft'))
```

* **Return type:**
  [`Tuple`](https://docs.python.org/3/library/typing.html#typing.Tuple)[[`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)], [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### scribed.textgrid.tier_named(tiers, names)

The name of the tier in `tiers` called one of `names` (any case, a
speaker’s prefix aside), by the order of `names`; None if there is none.

```pycon
>>> tier_named({"Carl - Words": [], "notes": []}, WORD_TIERS)
'Carl - Words'
```

* **Return type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### scribed.textgrid.trim_overlaps(intervals)

`intervals` sorted, each ending no later than the next begins.

For speakers talking over each other, which a single tier cannot hold. An
interval that is trimmed to nothing (it starts where another starts) is
dropped (of two intervals with the same start, the later-sorting one is kept).

```pycon
>>> trim_overlaps([(1, 3, "b"), (0, 2, "a")])
[(0, 1, 'a'), (1, 3, 'b')]
```

* **Return type:**
  [`List`](https://docs.python.org/3/library/typing.html#typing.List)[[`Tuple`](https://docs.python.org/3/library/typing.html#typing.Tuple)[[`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]

### scribed.textgrid.write_tiers(tiers, , xmax)

A long-form TextGrid of interval `tiers` spanning `0..xmax`.

What [`read_tiers()`](#scribed.textgrid.read_tiers) reads back, and what a forced aligner takes as a
transcript of timed lines. Gaps between intervals are filled with empty ones;
a `"` in a label or tier name is doubled. Times are rounded to
[`TIME_DECIMALS`](#scribed.textgrid.TIME_DECIMALS) places before they are checked. Nothing is clamped: an
interval outside `0..xmax`, empty, or overlapping another is a `ValueError`
(use [`trim_overlaps()`](#scribed.textgrid.trim_overlaps) first where overlap is expected). The reader strips
labels, so a label’s surrounding whitespace does not survive a round trip.

```pycon
>>> write_tiers({"take": [(0.5, 1.2, "a"), (1.0, 1.5, "b")]}, xmax=2.0)
Traceback (most recent call last):
  ...
ValueError: tier 'take': interval (1.0, 1.5, 'b') overlaps the one before, which ends at 1.2
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
