# scribed.readers

Read a transcript back into a [`Transcript`](scribed.base.html.md#scribed.base.Transcript).

scribed writes subtitles (`Transcript.srt` / `.vtt`); this module is the
reading direction, for a transcript that already exists: an SRT or WebVTT from a
recording session, a Praat TextGrid from an aligner, a word-timed JSON from an
earlier ASR run, or plain `speaker: text` lines (untimed):

```default
t = scribed.read_transcript("take1.srt")      # or Transcript.parse(...)
for seg in t:
    print(seg.speaker, seg.start, seg.end, seg.words)
```

The format is detected by file suffix, then by content; pass `fmt` to force one
of [`FORMATS`](#scribed.readers.FORMATS). A parsed transcript carries `backend="file:<fmt>"` so
downstream code can tell it from an ASR result. No dependencies.

```pycon
>>> t = read_transcript("1\n00:00:01,000 --> 00:00:02,500\n[carl] Hello there.\n")
>>> [(s.speaker, s.text, s.start, s.end) for s in t], t.backend
([('carl', 'Hello there.', 1.0, 2.5)], 'file:srt')
```

### Module Attributes

| [`FORMATS`](#scribed.readers.FORMATS)   | The transcript formats read here, in detection order.   |
|------------------------------------------------------------|---------------------------------------------------------|

### Functions

| [`detect_format`](#scribed.readers.detect_format)(text, \*[, suffix])   | Which of [`FORMATS`](#scribed.readers.FORMATS) `text` is: by file suffix first, then by content.   |
|--------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------|
| [`parse_timestamp`](#scribed.readers.parse_timestamp)(value)              | `HH:MM:SS,mmm` / `MM:SS.mmm` / plain seconds -> seconds.                                                              |
| [`read_transcript`](#scribed.readers.read_transcript)(source, \*[, fmt])  | Read `source` (a path to a transcript file, or the transcript text itself).                                           |

### scribed.readers.FORMATS *: [Tuple](https://docs.python.org/3/library/typing.html#typing.Tuple)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), ...]* *= ('vtt', 'textgrid', 'json', 'srt', 'plain')*

The transcript formats read here, in detection order.

### scribed.readers.detect_format(text, , suffix='')

Which of [`FORMATS`](#scribed.readers.FORMATS) `text` is: by file suffix first, then by content.

```pycon
>>> detect_format("WEBVTT\n\n00:01.000 --> 00:02.000\nhi")
'vtt'
>>> detect_format("1\n00:00:01,000 --> 00:00:02,000\nhi"), detect_format("hi there")
('srt', 'plain')
>>> detect_format('{"segments": []}'), detect_format("", suffix=".TextGrid")
('json', 'textgrid')
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### scribed.readers.parse_timestamp(value)

`HH:MM:SS,mmm` / `MM:SS.mmm` / plain seconds -> seconds.

```pycon
>>> parse_timestamp("00:01:02,500"), parse_timestamp("01:02.5"), parse_timestamp("7.25")
(62.5, 62.5, 7.25)
```

* **Return type:**
  [`float`](https://docs.python.org/3/builtins/functions.html#float)

### scribed.readers.read_transcript(source, , fmt=None)

Read `source` (a path to a transcript file, or the transcript text itself).

`fmt` (one of [`FORMATS`](#scribed.readers.FORMATS)) overrides detection. The result’s `backend`
is `"file:<fmt>"`.

```pycon
>>> t = read_transcript("carl: Hello.\nned: Hi.")
>>> t.speakers, t.backend, t.segments[0].span
(['carl', 'ned'], 'file:plain', None)
```

* **Return type:**
  [`Transcript`](scribed.base.html.md#scribed.base.Transcript)
