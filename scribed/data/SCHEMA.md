# scribed ledger schema (`backends.json`)

The ledger is a JSON object: `{"meta": {...}, "backends": [ {record}, ... ]}`.
Each record describes one ASR engine/service. Only `id` is strictly required;
everything else is best-effort curated research. Unknown/extra fields are kept
and exposed via `BackendInfo` attribute access, so the schema can grow without
code changes.

## Identity

| Field | Type | Meaning |
|---|---|---|
| `id` | str | Canonical id (dashes ok), e.g. `faster-whisper`. **Required.** |
| `name` | str | Short name used in tables. |
| `display_name` | str | Human-friendly name. |
| `homepage` | str | Project / docs / product URL. |

## Deployment & licensing

| Field | Type | Meaning |
|---|---|---|
| `is_local` | bool | Runs on the user's machine. |
| `is_remote` | bool | Hosted / cloud API. |
| `open_source` | bool | The engine itself is open source. |
| `license` | str | SPDX-ish license or `proprietary`. |
| `pricing_model` | str | `open_source` \| `free` \| `free_tier_then_paid` \| `paid`. |
| `price_note` | str | Human pricing summary, e.g. `"$0.0043/min (Nova-3)"`. |
| `price_per_min` | number\|null | Cheapest paid tier in USD/min, for ranking (null = free/local). |
| `api_env_var` | str\|list | Credential env var(s) for remote backends, else `""`. |
| `python_install` | str | `pip install ...` line (drives ledger-only scaffolding). |

## Capabilities (used by `catalog.can(...)` and `find`)

| Field | Type | Meaning |
|---|---|---|
| `streaming` | `"yes"`/`"no"`/`"limited"` | Real-time / incremental transcription. |
| `diarization` | `"yes"`/`"no"`/`"limited"` | Speaker labelling. |
| `word_timestamps` | `"yes"`/`"no"` | Word-level start/end times. |
| `translation` | `"yes"`/`"no"` | Speech translation (to English, usually). |
| `beyond_text` | list[str] | Extra outputs: `diarization`, `sentiment`, `topics`, `summary`, `translation`, `pii_redaction`, ... |

## Quality, coverage, speed

| Field | Type | Meaning |
|---|---|---|
| `accuracy_tier` | str | `baseline` \| `good` \| `high` \| `sota`. |
| `languages_count` | int | Approximate number of supported languages. |
| `languages_note` | str | Free-text coverage note (substring-searched by `supports_language`). |
| `speed_note` | str | RTF / latency / throughput note. |
| `max_audio` | str | File-size / duration limits note. |
| `output_formats` | list[str] | `text`, `segments`, `words`, `srt`, `vtt`, `json`. |

## Editorial

| Field | Type | Meaning |
|---|---|---|
| `best_for` | str | One-line "reach for this when…". |
| `pros` | list[str] | Selling points. |
| `cons` | list[str] | Caveats. |

## Computed (never stored)

`implemented` is added at load time by `Catalog` — `True` iff a real adapter
exists under `scribed.backends`. It is **not** part of the JSON; it is derived
live from the registry so the ledger can never lie about what scribed can run.
