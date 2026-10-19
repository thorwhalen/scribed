# scribed.backends.whispercpp.adapter

Adapter for the whisper.cpp backend (via the `pywhispercpp` binding).

Maps scribed’s normalized request onto `pywhispercpp.model.Model` and its
native `Segment` stream onto a [`scribed.base.Transcript`](scribed.base.html.md#scribed.base.Transcript). The engine is
imported and the model constructed lazily so `import scribed` stays
dependency-free; one `Model` is cached per requested size on the adapter.

whisper.cpp reports segment timestamps in *centiseconds* (1/100th of a second),
so `seg.t0` / `seg.t1` are divided by 100 to get seconds. There are no
per-word timestamps by default; a per-segment confidence (the geometric mean of
token probabilities, in `[0, 1]`) is surfaced when whisper.cpp computes it.

### Classes

| [`Adapter`](#scribed.backends.whispercpp.adapter.Adapter)(config)   | whisper.cpp adapter (caches one model per requested size).   |
|--------------------------------------------------------------------|--------------------------------------------------------------|

### *class* scribed.backends.whispercpp.adapter.Adapter(config)

Bases: [`BaseTranscriberAdapter`](scribed.make_backend.html.md#scribed.make_backend.BaseTranscriberAdapter)

whisper.cpp adapter (caches one model per requested size).
