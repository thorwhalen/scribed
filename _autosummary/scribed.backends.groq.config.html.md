# scribed.backends.groq.config

Configuration for the Groq (hosted Whisper) transcription backend.

Groq serves OpenAI’s Whisper models (`whisper-large-v3` and the faster
`whisper-large-v3-turbo`) on its LPU inference stack — extremely fast and
cheap. The HTTP API mirrors OpenAI’s audio-transcriptions endpoint, so
`response_format="verbose_json"` yields the same segment shape (`start`,
`end`, `text`, `avg_logprob`, `no_speech_prob`) and word/segment
timestamp granularities. `turbo` is the default for its speed/cost; switch to
`whisper-large-v3` for maximum accuracy.
