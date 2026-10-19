# scribed.backends.elevenlabs.adapter

Adapter for the ElevenLabs Scribe transcription backend.

Maps scribed’s normalized request onto `client.speech_to_text.convert` (model
`scribe_v1`) and the response onto a [`scribed.base.Transcript`](scribed.base.html.md#scribed.base.Transcript).

Scribe’s response has no segment structure: it returns the full `text` plus a
flat `words` stream where each item carries `text`, `start`/`end` (in
seconds), a `type` (`"word"` | `"spacing"` | `"audio_event"`) and — when
`diarize=True` — a `speaker_id`. This adapter filters the stream down to
actual words, then groups *consecutive* words by `speaker_id` into segments
(starting a new segment whenever the speaker changes). When no speaker ids are
present (e.g. `diarize=False`), all words form a single segment. The full
`resp.text` is always carried through as the authoritative transcript.

The client and credential are resolved lazily so `import scribed` stays
dependency-free.

### Classes

| [`Adapter`](#scribed.backends.elevenlabs.adapter.Adapter)(config)   | ElevenLabs Scribe transcription adapter (caches one client lazily).   |
|--------------------------------------------------------------------|-----------------------------------------------------------------------|

### *class* scribed.backends.elevenlabs.adapter.Adapter(config)

Bases: [`BaseTranscriberAdapter`](scribed.make_backend.html.md#scribed.make_backend.BaseTranscriberAdapter)

ElevenLabs Scribe transcription adapter (caches one client lazily).
