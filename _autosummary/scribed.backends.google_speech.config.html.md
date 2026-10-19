# scribed.backends.google_speech.config

Configuration for the Google Cloud Speech-to-Text (v1) backend.

Google Cloud Speech-to-Text is a hosted ASR API. This facade uses the v1
`long_running_recognize` endpoint for robustness with audio longer than a
minute, and decodes the input to mono LINEAR16 PCM (at the source sample rate)
so there is no format-guessing or resampling. It supports speaker diarization
and word-level time offsets.

Authentication uses Application Default Credentials: point
`GOOGLE_APPLICATION_CREDENTIALS` at a service-account JSON key file and the
client picks it up from the environment — no `api_key` is passed.

The normalized params map onto the fields the adapter uses to build a
`speech.RecognitionConfig`: `language` -> `language_code`,
`diarize` -> `diarize` (toggles `SpeakerDiarizationConfig`), and
`model` -> `model` (e.g. `"latest_long"`). The adapter consumes these
explicitly rather than forwarding them blindly, since not all map 1:1 onto the
config constructor.
