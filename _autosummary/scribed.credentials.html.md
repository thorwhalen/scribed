# scribed.credentials

Credential resolution for remote transcription backends.

Remote engines need an API key (or a path to a service-account JSON). Rather than
make each adapter reinvent the lookup, this module centralizes a small, layered
resolver:

1. an explicit value passed by the caller (`api_key=...`),
2. the backend’s declared environment variable(s),
3. (soft) a `.env` file discovered via `python-dotenv` if it is installed,
4. (optional) an interactive prompt, only in a REPL and only if asked.

A backend declares its variable(s) in `BACKEND_CONFIG['api_env_var']` (a string
or list). The well-known providers below give friendly defaults. The design
follows the credential pattern used by the sibling `aix` facade.

### Module Attributes

| [`PROVIDER_ENV_VARS`](#scribed.credentials.PROVIDER_ENV_VARS)   | Friendly provider -> canonical env-var name(s) for well-known services.                               |
|----------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| [`CREDENTIAL_GUIDANCE`](#scribed.credentials.CREDENTIAL_GUIDANCE) | Where/how to get a key, per provider — powers the dynamic "missing credential" errors AND the README. |

### Functions

| [`resolve_credential`](#scribed.credentials.resolve_credential)([provider, api_key, ...])   | Resolve a credential for a remote backend.                               |
|-------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| [`credential_help`](#scribed.credentials.credential_help)(provider)                      | A short, link-bearing 'how to get a key' message for `provider` (or ''). |

### Exceptions

| [`MissingCredentialError`](#scribed.credentials.MissingCredentialError)   | Raised when a required credential cannot be resolved.   |
|---------------------------------------------------------------------------|---------------------------------------------------------|

### scribed.credentials.CREDENTIAL_GUIDANCE *= {'assemblyai': {'env_var': 'ASSEMBLYAI_API_KEY', 'get_key_url': 'https://www.assemblyai.com/dashboard/signup', 'note': 'Create an account and copy your API key from the dashboard. Universal model with diarization, sentiment, topics; ~$0.0062/min (batch), free tier included.'}, 'aws-transcribe': {'env_var': 'AWS_ACCESS_KEY_ID (plus AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION)', 'get_key_url': 'https://docs.aws.amazon.com/transcribe/latest/dg/getting-started.html', 'note': 'Create AWS credentials (IAM user/role) with Transcribe permissions. Audio must usually be staged in S3 for batch jobs.'}, 'azure-speech': {'env_var': 'AZURE_SPEECH_KEY (plus AZURE_SPEECH_REGION)', 'get_key_url': 'https://learn.microsoft.com/azure/ai-services/speech-service/get-started-speech-to-text', 'note': 'Create a Speech resource in the Azure portal; copy its key and region. Supports batch and real-time, diarization, custom models.'}, 'deepgram': {'env_var': 'DEEPGRAM_API_KEY', 'get_key_url': 'https://console.deepgram.com/signup', 'note': 'Sign up and create an API key in the Deepgram console. Nova-3 is ~$0.0043/min with diarization, streaming, and word timestamps; includes $200 free credit.'}, 'elevenlabs': {'env_var': 'ELEVENLABS_API_KEY', 'get_key_url': 'https://elevenlabs.io/app/settings/api-keys', 'note': 'Create an API key in your ElevenLabs settings. Scribe v1 offers high-accuracy transcription with diarization and word timestamps.'}, 'fireworks': {'env_var': 'FIREWORKS_API_KEY', 'get_key_url': 'https://fireworks.ai/account/api-keys', 'note': 'Create an API key in the Fireworks dashboard; fast Whisper-v3.'}, 'gladia': {'env_var': 'GLADIA_API_KEY', 'get_key_url': 'https://app.gladia.io/', 'note': 'Create an API key in the Gladia dashboard; Whisper-based API.'}, 'google-speech': {'env_var': 'GOOGLE_APPLICATION_CREDENTIALS (or GOOGLE_API_KEY)', 'get_key_url': 'https://cloud.google.com/speech-to-text/docs/before-you-begin', 'note': 'Create a Google Cloud project, enable the Speech-to-Text API, create a service account, download its JSON key, and point GOOGLE_APPLICATION_CREDENTIALS at that file. Chirp models, 125+ langs.'}, 'groq': {'env_var': 'GROQ_API_KEY', 'get_key_url': 'https://console.groq.com/keys', 'note': 'Create an API key in the Groq console. Groq serves whisper-large-v3 and turbo extremely fast and cheap (~$0.02-0.04/hr of audio).'}, 'openai': {'env_var': 'OPENAI_API_KEY', 'get_key_url': 'https://platform.openai.com/api-keys', 'note': 'Create an API key in the OpenAI platform dashboard. Transcription uses whisper-1 / gpt-4o-transcribe at $0.006/min (whisper).'}, 'rev': {'env_var': 'REV_ACCESS_TOKEN', 'get_key_url': 'https://www.rev.ai/access_token', 'note': 'Create an access token in the Rev AI console.'}, 'speechmatics': {'env_var': 'SPEECHMATICS_API_KEY', 'get_key_url': 'https://portal.speechmatics.com/', 'note': 'Create an API key in the Speechmatics portal; batch + real-time.'}}*

Where/how to get a key, per provider — powers the dynamic “missing credential”
errors AND the README. Keep links current; these are user-facing.

### *exception* scribed.credentials.MissingCredentialError

Bases: [`RuntimeError`](https://docs.python.org/3/builtins/exceptions.html#RuntimeError)

Raised when a required credential cannot be resolved.

Its message includes provider-specific, link-bearing guidance on how to
obtain a key (see [`CREDENTIAL_GUIDANCE`](#scribed.credentials.CREDENTIAL_GUIDANCE)).

### scribed.credentials.PROVIDER_ENV_VARS *= {'assemblyai': ['ASSEMBLYAI_API_KEY'], 'aws-transcribe': ['AWS_ACCESS_KEY_ID'], 'azure-speech': ['AZURE_SPEECH_KEY'], 'deepgram': ['DEEPGRAM_API_KEY'], 'elevenlabs': ['ELEVENLABS_API_KEY', 'ELEVEN_API_KEY'], 'fireworks': ['FIREWORKS_API_KEY'], 'gladia': ['GLADIA_API_KEY'], 'google-speech': ['GOOGLE_APPLICATION_CREDENTIALS', 'GOOGLE_API_KEY'], 'groq': ['GROQ_API_KEY'], 'openai': ['OPENAI_API_KEY'], 'rev': ['REV_ACCESS_TOKEN'], 'speechmatics': ['SPEECHMATICS_API_KEY']}*

Friendly provider -> canonical env-var name(s) for well-known services.

### scribed.credentials.credential_help(provider)

A short, link-bearing ‘how to get a key’ message for `provider` (or ‘’).

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### scribed.credentials.resolve_credential(provider=None, , api_key=None, env_var=None, required=True, prompt_if_missing=False)

Resolve a credential for a remote backend.

* **Parameters:**
  * **provider** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – A known provider id (see [`PROVIDER_ENV_VARS`](#scribed.credentials.PROVIDER_ENV_VARS)) used to
    infer default env-var names.
  * **api_key** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – An explicit value; if given, it wins and is returned as-is.
  * **env_var** ([`Union`](https://docs.python.org/3/library/typing.html#typing.Union)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Sequence`](https://docs.python.org/3/library/typing.html#typing.Sequence)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)], [`None`](https://docs.python.org/3/builtins/constants.html#None)]) – Extra env-var name(s) to check (checked before provider defaults).
  * **required** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – If True (default), raise [`MissingCredentialError`](#scribed.credentials.MissingCredentialError) when
    nothing resolves; if False, return `None`.
  * **prompt_if_missing** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – If True and running interactively, prompt the user
    (via `getpass`) as a last resort.
* **Return type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]
* **Returns:**
  The resolved secret, or `None` when `required=False` and nothing was
  found.
