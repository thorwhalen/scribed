# scribed.backends.deepgram.adapter

Adapter for the Deepgram (Nova-3) transcription backend.

Maps scribed’s normalized request onto Deepgram’s pre-recorded REST endpoint and
the returned JSON onto a [`scribed.base.Transcript`](scribed.base.html.md#scribed.base.Transcript). The SDK and credential
are resolved lazily so `import scribed` stays dependency-free.

When `utterances=True` (always, here) Deepgram returns
`results.utterances` — one diarized speaker turn each, with nested words — and
we build one [`Segment`](scribed.base.html.md#scribed.base.Segment) per utterance (carrying
`speaker=str(utt.speaker)`). When utterances are absent we fall back to a single
segment built from `channels[0].alternatives[0]`. Deepgram reports times in
**seconds** and confidence already in `[0, 1]`, so no rescaling is needed.

The Deepgram Python SDK surface has shifted across major versions, so both the
SDK accessor and the response parsing here are deliberately defensive: we try the
v3 `listen.rest.v("1")` accessor first, fall back to the older
`listen.prerecorded.v("1")` one, and read response fields through `.to_dict()`
(falling back to `getattr`) so plain dicts and SDK objects are handled alike.

### Classes

| [`Adapter`](#scribed.backends.deepgram.adapter.Adapter)(config)   | Deepgram (Nova-3) transcription adapter.   |
|--------------------------------------------------------------------|--------------------------------------------|

### *class* scribed.backends.deepgram.adapter.Adapter(config)

Bases: [`BaseTranscriberAdapter`](scribed.make_backend.html.md#scribed.make_backend.BaseTranscriberAdapter)

Deepgram (Nova-3) transcription adapter.
