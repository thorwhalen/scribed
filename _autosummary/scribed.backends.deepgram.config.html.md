# scribed.backends.deepgram.config

Configuration for the Deepgram (Nova-3) transcription backend.

Deepgram’s hosted speech-to-text API. Nova-3 is a fast, accurate model with
diarization, word-level timestamps, and streaming — ~$0.0043/min with diarization
and $200 of free credit on signup.

The native kwargs declared here (`model`, `diarize`, `language`) are
forwarded by the adapter into `PrerecordedOptions`; the adapter additionally
sets `smart_format`, `punctuate` and `utterances` so that diarized speaker
turns come back as `results.utterances` (one [`scribed.base.Segment`](scribed.base.html.md#scribed.base.Segment)
each, carrying nested word-level timing).
