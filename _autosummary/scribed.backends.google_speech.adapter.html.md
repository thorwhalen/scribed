# scribed.backends.google_speech.adapter

Adapter for the Google Cloud Speech-to-Text (v1) backend.

Maps scribed’s normalized request onto `google.cloud.speech` and the response
onto a [`scribed.base.Transcript`](scribed.base.html.md#scribed.base.Transcript). The audio is decoded to a mono float32
waveform and re-encoded as int16 LINEAR16 PCM at the *source* sample rate (Google
accepts 8000-48000 Hz for LINEAR16, so no resampling is needed), which avoids
format/encoding guesswork. `long_running_recognize` is used for robustness with
audio longer than a minute.

The SDK and credentials are resolved lazily so `import scribed` stays
dependency-free. Google uses Application Default Credentials
(`GOOGLE_APPLICATION_CREDENTIALS`); the client picks them up from the
environment, so no `api_key` is passed.

### Module Attributes

| [`DFLT_LANGUAGE_CODE`](#scribed.backends.google_speech.adapter.DFLT_LANGUAGE_CODE)   | Language used when the caller does not specify one (Google requires a code).   |
|-----------------------------------------------------------------------|--------------------------------------------------------------------------------|
| [`DFLT_OP_TIMEOUT`](#scribed.backends.google_speech.adapter.DFLT_OP_TIMEOUT)      | Timeout (seconds) waiting on the long-running recognize operation.             |

### Classes

| [`Adapter`](#scribed.backends.google_speech.adapter.Adapter)(config)   | Google Cloud Speech-to-Text (v1) adapter.   |
|--------------------------------------------------------------------|---------------------------------------------|

### *class* scribed.backends.google_speech.adapter.Adapter(config)

Bases: [`BaseTranscriberAdapter`](scribed.make_backend.html.md#scribed.make_backend.BaseTranscriberAdapter)

Google Cloud Speech-to-Text (v1) adapter.

### scribed.backends.google_speech.adapter.DFLT_LANGUAGE_CODE *= 'en-US'*

Language used when the caller does not specify one (Google requires a code).

### scribed.backends.google_speech.adapter.DFLT_OP_TIMEOUT *= 600*

Timeout (seconds) waiting on the long-running recognize operation.
