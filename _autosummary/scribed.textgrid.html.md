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

```pycon
>>> grid = write_tiers({"take": [(0.5, 1.2, 'say "hi"')]}, xmax=2.0)
>>> read_tiers(grid)
{'take': [(0.0, 0.5, ''), (0.5, 1.2, 'say "hi"'), (1.2, 2.0, '')]}
```

### Module Attributes

| [`Interval`](#scribed.textgrid.Interval)      | `(start, end, label)`, in seconds.   |
|----------------------------------------------------------------|--------------------------------------|
| [`Tiers`](#scribed.textgrid.Tiers)         | `{tier name: intervals}`.            |
| [`TIME_DECIMALS`](#scribed.textgrid.TIME_DECIMALS) | the reader takes no exponent).       |

### Functions

| [`read_tiers`](#scribed.textgrid.read_tiers)(text)             | `{tier name: [(start, end, label), ...]}` for every interval tier (long or short form).   |
|-------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------|
| [`write_tiers`](#scribed.textgrid.write_tiers)(tiers, \*, xmax) | A long-form TextGrid of interval `tiers` spanning `0..xmax`.                              |
| [`trim_overlaps`](#scribed.textgrid.trim_overlaps)(intervals)     | `intervals` sorted, each ending no later than the next begins.                            |

### scribed.textgrid.Interval

`(start, end, label)`, in seconds.

alias of `Tuple`[[`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### scribed.textgrid.TIME_DECIMALS *= 6*

the reader takes no exponent).

* **Type:**
  Decimal places written for a time (fixed-point

### scribed.textgrid.Tiers

`{tier name: intervals}`.

alias of [`Dict`](https://docs.python.org/3/library/typing.html#typing.Dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`List`](https://docs.python.org/3/library/typing.html#typing.List)[`Tuple`[[`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]]

### scribed.textgrid.read_tiers(text)

`{tier name: [(start, end, label), ...]}` for every interval tier (long or short form).

Labels are stripped; a doubled `""` is a quote.

```pycon
>>> read_tiers(write_tiers({"a": [(0, 1, "x")]}, xmax=1))
{'a': [(0.0, 1.0, 'x')]}
```

* **Return type:**
  [`Dict`](https://docs.python.org/3/library/typing.html#typing.Dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`List`](https://docs.python.org/3/library/typing.html#typing.List)[[`Tuple`](https://docs.python.org/3/library/typing.html#typing.Tuple)[[`float`](https://docs.python.org/3/builtins/functions.html#float), [`float`](https://docs.python.org/3/builtins/functions.html#float), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]]

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
