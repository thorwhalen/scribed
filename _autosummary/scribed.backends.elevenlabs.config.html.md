# scribed.backends.elevenlabs.config

Configuration for the ElevenLabs Scribe transcription backend.

Uses ElevenLabs’ hosted `speech_to_text.convert` endpoint with the
`scribe_v1` model. Scribe returns the full text plus a flat `words` stream
(each word carrying `start`/`end` in seconds, a `type` of
`word`/`spacing`/`audio_event`, and — when `diarize=True` — a
`speaker_id`). There is no segment structure in the response; the adapter
builds segments by grouping consecutive `word` items by `speaker_id`.
