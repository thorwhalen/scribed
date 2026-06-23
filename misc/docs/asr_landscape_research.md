# Speech-to-Text / ASR Engine Landscape (2025–2026)

**Research date: 2026-06-23.** Compiled to inform a Python *façade* package — "one API over many transcription engines" — modeled on an OCR-façade library, with a browsable catalog/ledger and ~10 implemented backends.

**How to read this report.** Every number is tagged for provenance: **[vendor]** = self-reported (treat as marketing), **[independent]** = neutral third party (Hugging Face Open ASR Leaderboard, Artificial Analysis, Picovoice, academic papers), **[repo]** = project's own benchmark with reproducible code. Pricing was taken off live vendor pages on 2026-06-23 and **drifts quarterly** — keep it in external config, never hardcode. WER numbers from different benchmarks are **not comparable** (different audio); always state the suite.

---

## 0. Executive summary (the load-bearing findings)

1. **The accuracy/speed frontier is no longer Whisper.** NVIDIA's **Parakeet** (CC-BY-4.0, local) and **Canary** models now top the independent Open ASR Leaderboard on *both* accuracy and throughput; Parakeet-TDT-0.6B-v2 hits ~6.05% WER at ~3,380× real-time on a single A100 — far faster *and* more accurate than Whisper-large-v3.
2. **For a façade, the hard problem is interface normalization, not picking engines.** The axes that actually hurt: timestamp encoding (Azure uses 100-ns ticks; Google uses `"1.2s"` strings), the diarization-vs-channels split, the sync / async-poll / streaming job model, the cloud-storage-upload gate (Google/AWS/Azure batch), and wildly different billing units (per-second, per-token, per-compute-second, per-"Neuron", $0).
3. **OpenAI-compatible is the cheapest path to many engines.** OpenAI, Groq, and Fireworks all speak the same `audio.transcriptions.create(...)` shape — one adapter covers three+ backends.
4. **Several "known facts" are now stale:** OpenAI **added diarization** (`gpt-4o-transcribe-diarize`); AssemblyAI's **Slam-1 is deprecated** (→ Universal-3 Pro); Deepgram **inverted** streaming-vs-batch pricing (streaming now cheaper); ElevenLabs **Scribe v1 EOL July 2026** (→ v2); **Fireworks audio is deprecated** (changelog 2026-06-10); Coqui/DeepSpeech are **dead**.
5. **Cheapest cloud:** Cloudflare Workers AI Whisper (~$0.00045/audio-min ≈ $0.027/hr) and Groq Whisper-turbo (~$0.04/hr) are an order of magnitude below the premium clouds — but both are batch-only with no diarization.

---

## 1. Big comparison table

Legend: **L** = local, **R** = remote/cloud. Streaming/Diar/WordTS: Y/N/partial. "$/hr audio" is a rough batch/pre-recorded list rate for cheapest-first ranking (see §3). WER is tagged with its source; treat cross-row WER comparisons with caution.

### 1a. Local / open-source engines

| Engine | L/R | License | $/hr | Speed (provenance) | Stream | Diar | WordTS | Langs | WER signal | Install burden | Python call | Output |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **OpenAI Whisper** (PyTorch; large-v3 / turbo) | L | MIT (code); HF large-v3 card = Apache-2.0, turbo = MIT | $0 + compute | turbo "relative 8×"; RTFx ~200 [vendor card] | N | N | Y (attention trick, approx) | 99 | ~7.4% large-v3, ~7.8% turbo [independent, Open ASR-derived] | pip + **ffmpeg**; weights ~1.5GB; GPU for large | `whisper.load_model("turbo").transcribe("a.mp3")` | dict: `text`, `language`, `segments[]`, words via flag |
| **whisper.cpp** | L | MIT | $0 + compute | ~8–10× RT large-v3 GPU/Metal [independent blog] | partial (mic `stream`) | partial (tinydiarize, 2-spk) | Y (token, exp) | ~99 | = Whisper weights (quant drift) | **CMake build**; ggml/GGUF weights; no Torch | C/C++ + CLI; 3rd-party py bindings (`pywhispercpp`) | text + SRT/VTT/JSON |
| **faster-whisper** (CTranslate2) | L | MIT | $0 + compute | **4× vs openai-whisper** [repo]; +2–4× batched; ~12× RT large-v3 RTX4070 [independent] | N (lazy gen only) | N | Y | 99 | = Whisper (int8 minor drift) | pip; GPU needs cuBLAS+cuDNN; PyAV decodes | `WhisperModel("large-v3").transcribe("a.mp3")` | `(segments_gen, info)`; `seg.words` |
| **WhisperX** | L | BSD-2 (pyannote diar = CC-BY-4.0, gated) | $0 + compute | **70× RT large-v2** [repo, GPU unstated] | N | **Y** (pyannote) | **Y** (wav2vec2 forced align) | 99 transcribe / ~5 align defaults | = faster-whisper + better timing | pip; CUDA/cuDNN/ffmpeg + **HF token** | multi-step: transcribe→align→diarize | dict `segments[]`→`words[]`+`speaker` |
| **distil-whisper** (distil-large-v3.5) | L | MIT | $0 + compute | **6.3× vs large-v3** [vendor card] | N | N | Y | **English only** | OOD WER 7.08 short / 11.39 long [vendor card, Open ASR method] | pip transformers; multi-backend | `pipeline("asr", model="distil-whisper/distil-large-v3.5")` | `{text, chunks:[{text,timestamp}]}` |
| **NeMo Parakeet-TDT-0.6B-v2** | L | CC-BY-4.0 | $0 + compute | **RTFx ~3,380–3,390** (bs128) [vendor card + independent agree] | offline | N | **Y** (word/seg/char) | EN (v3=25) | **WER 6.05** [independent Open ASR] | **heavy** (NeMo+Torch); GPU for speed | `ASRModel.from_pretrained(...).transcribe(['a.wav'])` | Hypothesis: `.text`, `.timestamp` |
| **NeMo Canary-Qwen-2.5B** | L | CC-BY-4.0 | $0 + compute | **RTFx 418** [independent] | offline | N | not documented | EN | **WER 5.63 — #1 open** [independent Open ASR] | heavy (NeMo git); GPU | SALM `.generate(prompts=[...audio...])` | LLM text (ASR or summarize mode) |
| **NeMo Canary-1B-v2** | L | CC-BY-4.0 | $0 + compute | RTFx 749 [independent] | offline | N | Y | **25** (+ translation) | WER 7.15 [independent] | heavy; GPU | `.transcribe(['a.wav'], source_lang=, target_lang=)` | text + word/seg TS |
| **wav2vec2** (HF transformers) | L | Apache-2.0 | $0 + compute | fast single-pass CTC; not on leaderboard | chunked | N | Y (`return_timestamps="word"`) | EN (XLSR/MMS = many) | LS clean 1.9 / other 3.9 [vendor card]; weak real-world | **lightest** (pip transformers); CPU-OK | `pipeline("asr", model="facebook/wav2vec2-large-960h-lv60-self")` | `{text, chunks}`; UPPERCASE, no punct |
| **Vosk** (Kaldi) | L | Apache-2.0 | $0 + compute | real-time on CPU; ~50MB models | **Y** (streaming-first) | speaker ID (x-vector) | Y (`SetWords(True)`) | 20+ | footprint-optimized; below Conformers | pip + model zip; **no CUDA/CPU** | `KaldiRecognizer(model,16000)` feed PCM | JSON `{text, result:[{word,start,end,conf}]}` |
| **Silero STT** | L | **CC-BY-NC** (mostly; some MIT) | $0 + compute | fast on CPU | N | N | N | en/de/es | none published | pip torch + `torch.hub` | `torch.hub.load('snakers4/silero-models','silero_stt')` | **plain text** |
| **SpeechBrain** | L | Apache-2.0 | $0 + compute | Conformer recipes competitive | recipe-level | **Y** | via alignment | many | recipe-dependent | pip + torch; HF weights | `EncoderDecoderASR.from_hparams(...).transcribe_file("a.wav")` | plain text (structured via alignment) |
| **Sherpa-ONNX** (k2/next-gen Kaldi) | L | Apache-2.0 | $0 + compute | model-dependent (can run Parakeet/Zipformer) | **Y** (streaming-first) | **Y** | **Y** | many | hosts top models | **light** pip; **CPU, no GPU/Torch** | `OfflineRecognizer.from_transducer(...)` | result `.text`, `.timestamps` |
| **Moonshine** (edge) | L | MIT | $0 + compute | up to **43.7× vs Whisper-large-v3** [vendor] | **Y** (first-class) | experimental | N (not documented) | 8 (STT) | Medium-stream 6.65% vs Whisper-v3 7.44% [vendor] | pip; **ONNX**, no Torch; edge-first | `Transcriber(...).add_audio(chunk,sr)` | text (incremental partial/final) |
| **Ultravox** (audio LLM — **not ASR**) | L | MIT + base-LLM license | $0 + heavy compute | ~150ms TTFT (8B) [vendor] | Y (agent) | N | N | ~42 | **N/A — no WER** (generative) | heavy (70B/8B backbone); GPU | HF pipeline `{audio, turns:[...]}` | text **answer**, not transcript |
| **Kaldi** (classic) | L | Apache-2.0 | $0 + compute | recipe-dependent | Y (online decoders) | Y (x-vector) | Y (lattice/CTM) | recipe-based | recipe-dependent | **heaviest (C++ compile)** | shell binaries (no 1st-class py) | CTM/lattice |
| **Coqui STT / Mozilla DeepSpeech** | L | Apache/MPL-2.0 | $0 + compute | single-pass | partial | N | Y | EN-centric | **DEAD** (DeepSpeech archived Jun 2025; Coqui shut Dec 2025) | medium | `Model("m.pbmm").stt(audio)` | plain text |

### 1b. Cloud / API engines

| Engine | L/R | Open? | $/hr (batch) | Speed (provenance) | Stream | Diar | WordTS | Langs | WER signal | Auth/SDK | Python call | Output unit & terms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **OpenAI** whisper-1 / gpt-4o-transcribe / -mini | R | whisper-1 hosts open wts; 4o closed | $0.36/hr ($0.006/min); **mini $0.18/hr** ($0.003) | gpt-4o ~31.9× RT [independent AA] | Y (4o; Realtime API) | **Y** (new `-diarize` model) | Y (whisper-1 verbose_json) | ~99 | gpt-4o ~4.0% [independent AA] | Bearer key; `openai` | `client.audio.transcriptions.create(model=,file=)` **sync, file ≤25MB, no URL** | `text`; verbose_json: `segments`→`words` |
| **Groq** (Whisper v3 / turbo / distil) | R | hosts open wts | turbo **$0.04/hr**; v3 $0.111/hr | **164–228× RT** [vendor, AA-validated] | **N** | N | Y (verbose_json) | ~99 | v3 ~10.3% [vendor mix] | Bearer; `groq` (OpenAI-compat) | same shape; `url=` param (100MB) | OpenAI-compat: `text`,`segments`,`words` |
| **Deepgram** Nova-3 / Nova-2 | R + **on-prem** | proprietary | **$0.26/hr** prerec ($0.0043); stream $0.46/hr ($0.0077)** | ~477× RT [independent AA]; "40× faster diar" [vendor] | **Y** (WebSocket) | Y (**+$0.002/min add-on**) | Y + confidence | 50+ (Nova-3) | 5.26% [vendor own set] | `Token` header; `deepgram-sdk` (**v7 ≠ v3/v4**) | `transcribe_url`/`transcribe_file`; WS | `channels[]→alternatives[]→words[]`; `utterances`,`paragraphs`; speaker **int** |
| **AssemblyAI** Universal-3 Pro / Universal-Streaming | R | proprietary | **U3-Pro $0.21/hr**; U2 $0.15/hr | ~100× RT [independent AA]; ~300ms stream [vendor] | **Y** (Universal-Streaming) | Y (**+$0.02/hr**, `speaker_labels`) | Y (ms) | ~99 async / 6 stream | U3-Pro ~3.1% [independent AA] | raw key (no Bearer); `assemblyai` | `Transcriber().transcribe(url)` **async submit→poll (hidden)** | flat `text`+`words[]`+`utterances[]`; speaker **str "A"/"B"** |
| **ElevenLabs Scribe** (v2 / v2-realtime) | R | proprietary | **$0.22/hr** (v2); realtime $0.39/hr | Scribe v2 33.9× RT [independent AA]; realtime ~150ms | **Y** (v2-realtime, ~150ms) | **Y** (up to **32 spk**, included) | Y (+ char-level) | 90+ | **2.2% — #1** [independent AA] | `xi-api-key`; `elevenlabs` | `speech_to_text.convert(model_id="scribe_v2",file=)` sync (`webhook=True` async) | `words[]` w/ `type` (word/spacing/**audio_event**); `speaker_id` str |
| **Speechmatics** (Ursa/Melia) | R + **true on-prem** | proprietary | **Melia $0.129/hr**; Std $0.24/hr | real-time <1s [vendor] | **Y** | Y (**included**) | Y | 55+ transcribe | Enhanced 11.96% [vendor own] | Bearer; modular `speechmatics-batch`/`-rt` (**SDK rewritten**) | batch async job; RT WebSocket | `results[]→alternatives[]` item-level; speaker **str "S1"/"S2"/"UU"** |
| **Gladia** (Solaria) | R (Ent on-prem) | own model (was Whisper-Zero) | Starter **$0.61/hr**; Growth ~$0.20/hr | ~103ms partial [vendor] | **Y** (live WS) | Y (included) | Y | 100 | ~6% [vendor] | `x-gladia-key`; `gladiaio-sdk` | `POST /v2/pre-recorded` **submit→poll** | `transcription→utterances[]→words[]`; speaker **int** |
| **Google Cloud STT** (Chirp 2/3, V2) | R + on-prem (GKE) | proprietary | **$0.96/hr** ($0.016/min); Dynamic Batch ~$0.004/min | no headline | **Y** (gRPC) | Y (config; not Chirp-3 stream) | Y (**NOT Chirp-3**) | ~99 | ~8.9% [independent Picovoice, pre-Chirp] | SA JSON / ADC; `google-cloud-speech` | `Recognize` sync / `BatchRecognize` LRO; **`gs://` for long** | `results[]→alternatives[]→words[]`; per-15-sec billing |
| **AWS Transcribe** | R | proprietary | **batch $0.36/hr** ($0.006/min); stream $0.60/hr ($0.01) | "~120× RT diar" [vendor] | **Y** (HTTP/2 + WebSocket) | Y (`ShowSpeakerLabels`, XOR channels) | Y | 100+ batch / fewer stream | **~4.3% — best cloud** [independent Picovoice] | IAM; `boto3` / `amazon-transcribe` | `start_transcription_job(Media={MediaFileUri:s3://})` **poll**; **S3 required** | `results.items[]` (`type`); per-second (15s min) |
| **Azure AI Speech** | R + **on-prem containers** | proprietary | **batch ~$0.36/hr**; real-time **$1.00/hr**; fast ~$0.66/hr | low-latency [vendor] | **Y** (SDK) | Y (free on fast) | Y (ticks) | **140+** | ~5.5% [independent Picovoice] | key+region / Entra; `azure-cognitiveservices-speech` | `SpeechRecognizer.recognize_once()`; batch REST poll | **`NBest[]`**→`Display`/`Words` **100-ns ticks**; per-second |
| **Rev.ai** (Reverb + Whisper) | R + on-prem (ent) | Reverb open (non-commercial) | **Reverb Turbo $0.10/hr**; Reverb $0.20/hr; Whisper $0.30/hr | async ~5min [vendor] | **Y** (WS + RTMP) | Y (**default, free**) | Y | 58+ async / 9 stream | Reverb 9.68 vs Whisper-v3 14.26 Earnings21 [vendor paper] | Bearer; `rev-ai` | `submit_job_url()` **poll** | `monologues[]→elements[]` (`ts`/`end_ts`); speaker int |
| **Fireworks AI** (hosted Whisper) **⚠️ DEPRECATED 2026-06-10** | R | hosts open wts | turbo **$0.054/hr**; v3 $0.09/hr | "1hr in <4s" ~900× [vendor] | Y (WS) | Y (batch only) | Y | 95+ | = Whisper-v3 (LS 2.0%) [vendor] | Bearer; `fireworks-ai` / OpenAI-compat | OpenAI-compat; file or URL | `segments[]`,`words[]` (+`hallucination_score`) |
| **Replicate** (hosted Whisper) | R | hosts open wts | **per compute-second** (~$0.001–0.003+/short run) | incredibly-fast ~90× RT [vendor] | **N** | Y (pyannote, optional) | Y | ~99 | = whisper-v3 | `REPLICATE_API_TOKEN`; `replicate` | `replicate.run(model, input={audio:url})` | **inconsistent**: `transcription`/`segments` OR `text`/`chunks`/`speakers` |
| **Cloudflare Workers AI** (Whisper / turbo) | R (edge) | hosts open wts | **~$0.027/hr** ($0.00045/min); 10k Neurons/day free | edge, no cold-start | **N** | **N** | Y + `vtt` | ~99 | = Whisper | token + account-id; REST/binding | REST `--data-binary @a.mp3` (base/turbo differ) | base: `text`,`words[]`,`vtt`; turbo nests differently |
| **IBM Watson STT** | R + on-prem (Cloud Pak) | proprietary | **Plus $1.20/hr** ($0.02/min); $0.01 >1M min | no published RTF | **Y** (WS) | Y (`speaker_labels`, ~6 langs) | Y | ~10+ | **~22% — worst** [independent Picovoice] | IAM; `ibm-watson` | `stt.recognize(audio=, model=)` sync / async job / WS | `results[]→alternatives[]`; per-minute |

---

## 2. Terminology & interface differences (façade data-model design)

This is the core design input. Each ASR system names and structures the same concepts differently; the façade must abstract over **eight axes of variation**.

### 2.1 The transcription UNIT (the central fault line)

Every vendor nests transcription differently. Canonical hierarchy to adopt: **Transcript → Segment/Utterance → Word → (optional) Alternative**.

| Vendor | Top container | "Best text" path | Word unit | N-best |
|---|---|---|---|---|
| Whisper / faster-whisper | `segments[]` | `text` | `words[]` (flag) | none |
| OpenAI gpt-4o | flat `text` (json); `segments`+`words` only in verbose_json (whisper-1) | `text` | `words[]` | none |
| Google | `results[]`→`alternatives[]` | `results[].alternatives[0].transcript` | `alternatives[0].words[]` (`WordInfo`) | `alternatives[]` (per-result) |
| AWS | `results.items[]` + `audio_segments[]` | `results.transcripts[0].transcript` | **`items[]`** (`type: pronunciation`/`punctuation`) | per-token `items[].alternatives[]` |
| Azure | **`NBest[]`** | `NBest[0].Display` / top-level `DisplayText` | `NBest[].Words[]` | `NBest[]` — **`NBest[0]` not guaranteed highest-conf** |
| Deepgram | `results.channels[]→alternatives[]` | `channels[0].alternatives[0].transcript` | `alternatives[0].words[]` + `paragraphs`/`utterances` | `alternatives[]` |
| AssemblyAI | flat `text`+`words[]`+`utterances[]` | `text` | `words[]` | none |
| Speechmatics | `results[]` (each word/punct w/ `alternatives[]`) | concat `results[].alternatives[0].content` | `results[]` items | per-token `alternatives[]` |
| ElevenLabs | `words[]` (word + audio-event) | `text` | `words[]` (`type: word`/`spacing`/`audio_event`) | none |
| Gladia | `transcription→utterances[]` | `full_transcript` | `utterances[]→words[]` | none |
| Rev.ai | `monologues[]→elements[]` | concat `elements[].value` | `elements[]` (`type: text`/`punct`) | none |

**Synonyms that all mean "a chunk":** `segment` (Whisper), `result` (Google/Speechmatics/IBM), `item` (AWS), `NBest`/`phrase`/`recognizedPhrase` (Azure), `utterance`/`paragraph` (Deepgram/AssemblyAI/Gladia), `monologue` (Rev). **"alternative"** consistently means an n-best hypothesis but attaches at different levels (per-utterance in Google/Azure, **per-token** in AWS-batch/Speechmatics). **Design:** model "best transcript per segment" + an **optional raw-alternatives passthrough**; treat punctuation as a distinct token type (it carries no timestamp in several vendors).

### 2.2 Speaker DIARIZATION vs CHANNELS (keep orthogonal)

Two genuinely different concepts:
- **Diarization (cluster-based):** ML infers "who spoke" on one mixed channel → labels `spk_0`, `"A"`, `1`, `"Guest-1"`, `"S1"`.
- **Channel identification (deterministic):** one speaker per physical channel (stereo call legs) → `ch_0`/`ch_1`.

| Vendor | How enabled | Speaker label form | Cost |
|---|---|---|---|
| Deepgram | `diarize=true` (**flag**) | `speaker` **int** + confidence | **+$0.002/min** |
| AssemblyAI | `speaker_labels=true` (**flag**) | `"A"`,`"B"` **str** | **+$0.02/hr** |
| Google | `diarizationConfig` (**config object**) | `speakerLabel` per word, **last result only** | base |
| Azure | `ConversationTranscriber` / `diarization.enabled` (config) | `speaker_id` `"Guest-1"` / int | included (free on fast) |
| Speechmatics | `diarization: "speaker"` (config) | **str** `"S1"/"S2"/"UU"` | **included** |
| ElevenLabs | `diarize` param | `speaker_id` str (up to **32**) | **included** |
| Gladia | `diarization: true` | **int** | included |
| Rev.ai | **default on** | int | **free** |
| OpenAI | **separate model** `gpt-4o-transcribe-diarize` | per-segment `speaker` | model-specific |
| Whisper/Parakeet (local) | **none built-in** (needs pyannote/WhisperX) | — | — |

**Design:** `speaker: str | None` **and** `channel: int | None` as two independent optional fields, never collapsed. Diarization is variously a **flag**, a **config object**, a **separate model**, or **unavailable locally**.

### 2.3 TIMESTAMPS — three incompatible encodings

| Vendor | Representation | Unit |
|---|---|---|
| Whisper / faster-whisper / OpenAI / Deepgram / Speechmatics / ElevenLabs / Gladia | `start`/`end` floats | **seconds** |
| Google | `startOffset`/`endOffset` as `"1.200s"` strings (Duration) | **seconds (string)** |
| AWS batch | `start_time`/`end_time` as **strings** `"1.09"` | **seconds (string)** |
| AWS streaming | `StartTime`/`EndTime` numbers | **seconds (float)** |
| Azure real-time/SDK | `Offset`/`Duration` | **100-ns TICKS** (1s = 10,000,000) |
| Azure fast | `offsetMilliseconds`/`durationMilliseconds` | **milliseconds** |
| Azure batch | `offsetInTicks` **and** `offset` (`"PT0.76S"` ISO-8601) | **ticks AND ISO-8601** |
| AssemblyAI | `start`/`end` | **milliseconds (int)** |

Also **offset+duration (Azure) vs start+end (everyone else)**. **Design:** normalize to **float seconds at ingest** via a per-vendor `to_seconds()` — parse Google's `"…s"` strings, `float()` AWS strings, `÷1e7` Azure ticks, `÷1e3` ms, parse ISO-8601 `PTxS`. This is one of the three hardest normalization axes.

### 2.4 INTERFACE / JOB MODEL — three patterns

1. **Synchronous recognize (short audio):** OpenAI, Groq, Fireworks, Cloudflare, IBM sync, Google `Recognize` (≤1min), Azure Fast Transcription, local engines. Transcript returned in the HTTP response / function return.
2. **Asynchronous job + poll (long audio):** AWS `StartTranscriptionJob`→poll `GetTranscriptionJob`; Google `BatchRecognize`→`Operation`; Azure Batch; AssemblyAI/Gladia/Rev/Speechmatics submit→poll. SDKs often **hide** the polling behind a blocking `.transcribe()`.
3. **Real-time streaming:** WebSocket (Deepgram, AssemblyAI, ElevenLabs, Speechmatics, Gladia, AWS, Rev, IBM, Fireworks); gRPC (Google); SSE (OpenAI gpt-4o `stream=true`). **None:** Replicate, Cloudflare, Groq, OpenAI file endpoint.

Vendor terms: Deepgram **"pre-recorded" vs "streaming"**; AWS/Azure **"batch" vs "streaming"**. Streaming partials carry an `is_final` / `IsPartial` flag. **Note AWS has no inline short-sync recognize** — a 10-second clip must go through S3 batch or a stream. **Design:** expose `mode: sync | batch | stream` enum, auto-select by audio length + engine capability; surface `is_final` on streamed segments.

### 2.5 Audio INPUT model — the cloud-storage gate

| Vendor | bytes | path | public URL | cloud-storage URI | Long audio needs cloud storage? |
|---|---|---|---|---|---|
| Google | base64 (short) | — | — | `gs://` | **Yes** (batch) |
| AWS | (stream chunks) | — | — | **`s3://`** | **Yes** (batch S3-only) |
| Azure | bytes (fast/short) | — | `contentUrls[]` | Blob + **SAS** | **Yes** (batch) |
| Deepgram / AssemblyAI / OpenAI / ElevenLabs / Speechmatics / Gladia / Rev / Fireworks / IBM | ✔ (various) | ✔ (SDK) | ✔ (most) | — | No |
| Cloudflare | bytes/base64 | — | — | — | No (chunk client-side) |
| Replicate | — | file handle | URL/data-URI | — | No |
| Local | array/bytes | **path** | — | — | No |

**Caps:** OpenAI **25 MB hard cap** (forces chunking); Google 480min batch; AWS 8h/2GB; Azure 240min/file w/ diarization. **Design:** accept a permissive input union (`bytes | path | URL | gs:// | s3://`) and auto-route; for cloud-storage-gated engines, require a URI past a threshold or transparently upload.

### 2.6 UNIT OF BILLING — and rounding

| Vendor | Unit | Rounding / minimum |
|---|---|---|
| Google | per second | up to 1s, no min (legacy 15s) |
| AWS | per second | up, **15s per-request min** |
| Azure | per second (quoted $/hr) | 1s increments |
| Deepgram | per minute (stream) / per hour (prerec) | per-second metering |
| AssemblyAI | per second | streaming billed on **session duration**, not audio |
| Speechmatics | per audio-minute | 12×5s clips cost same as one 60s file |
| OpenAI whisper-1 | per minute | rounded |
| OpenAI gpt-4o | **per audio-minute OR per token** ($2.50/M in, $10/M out) | dual |
| Groq | per second | **10s per-request min** |
| ElevenLabs / IBM | per minute | — |
| Cloudflare | **per "Neuron"** ($0.011/1k) | 10k/day free |
| Replicate | **per compute-second** (wall-clock GPU) | + billed 30–120s cold start |
| Local | **$0** + compute | — |

**Design:** model a per-engine cost function `(unit, rate, min_billable, rounding)`; special-case token-billed (gpt-4o), compute-second-billed (Replicate), neuron-billed (Cloudflare). Normalize to **$/audio-minute** for *comparison* but keep the native unit for *estimation*.

### 2.7 Cross-cutting features

- **Confidence:** float `[0,1]` mostly, but **AWS batch returns it as a string**; Google/Azure populate per-alternative confidence **only for the top hypothesis**; Whisper emits **logprob**, not calibrated 0–1. Normalize to `confidence: float | None`; don't assume presence.
- **Language detection:** Google `alternativeLanguageCodes`/v2 `languageCodes`; AWS `IdentifyLanguage`; Azure `AutoDetectSourceLanguageConfig`; AssemblyAI `language_detection`; Whisper auto. Normalize to `language` + `language_confidence`.
- **Formatting:** **Azure's four text forms** (`Lexical` raw / `ITN` "5" / `MaskedITN` / `Display` capitalized+punctuated) is the richest model — a good template for a façade "raw vs display" distinction. Others: `enableAutomaticPunctuation` (Google), `smart_format` (Deepgram), `format_text` (AssemblyAI). Profanity filter is a flag everywhere.
- **Custom vocab:** Google `PhraseSet`+`boost`; AWS `VocabularyName`; Azure `PhraseListGrammar`; Deepgram `keywords`/`keyterm`; AssemblyAI `word_boost`; OpenAI `prompt`. Normalize to `vocabulary: list[str]` (+ optional per-term boost).

### 2.8 Summary — the eight axes a façade adapter must abstract

1. Output nesting & unit names (results/alternatives/words vs items vs NBest vs channels vs flat).
2. Timestamp encoding (sec-float / sec-string / `"1.2s"` / 100-ns ticks / ms / ISO-8601; start-end vs offset-duration).
3. Diarization vs channels (flag / config / separate model / unavailable; int vs str labels).
4. Confidence presence & type (float vs string; top-only vs all; logprob vs 0–1).
5. Interface mode (sync / async-poll / streaming; partial flags).
6. Audio input + cloud-storage gate (bytes/path/URL vs `gs://`/`s3://`/SAS; size caps).
7. Billing unit (per-sec/min/hr / per-token / per-compute-sec / per-neuron / $0).
8. Formatting & features (raw-vs-display, punctuation/profanity, language detect, custom vocab).

**Recommended canonical model:**
```
Transcript{ full_text, language, language_confidence, duration_s, segments[], words[], engine, raw }
Segment{ text, start_s: float, end_s: float, speaker: str|None, channel: int|None,
         words[], confidence: float|None, alternatives[]? }
Word{ text, start_s: float, end_s: float, confidence: float|None,
      speaker: str|None, channel: int|None, is_punctuation: bool }
```
Keep the untouched vendor payload in `raw` as a lossless escape hatch. Model `speaker`/`channel` as orthogonal optionals; normalize all times to float seconds; expose `mode` and a per-engine cost function.

---

## 3. Pricing deep-dive (cheapest-first)

Rough **$/hour of audio**, batch/pre-recorded list rates, single channel. **Verify live before contracting.** Provenance: vendor pricing pages, 2026-06-23.

| Rank | Engine | ~$/hr | Notes |
|---|---|---|---|
| 0 | **Local** (Whisper, faster-whisper, Parakeet, whisper.cpp, Vosk, sherpa-onnx, …) | **$0** + compute | only hardware/electricity; Parakeet & Whisper weights free |
| 1 | **Cloudflare Workers AI** Whisper | **~$0.027/hr** ($0.00045/min) | cheapest cloud; **no diar, no stream**; 10k Neurons/day free; undated rounding |
| 2 | **Groq** Whisper-turbo | **$0.04/hr** | cheapest *fast* cloud; batch-only, no diar; 10s min/request |
| 3 | **Fireworks** Whisper-turbo | $0.054/hr | **⚠️ deprecated 2026-06-10** |
| 4 | **Fireworks** Whisper-v3 | $0.09/hr | ⚠️ deprecated |
| 5 | **Rev.ai** Reverb Turbo | $0.10/hr | Reverb weights non-commercial |
| 6 | **Groq** Whisper-large-v3 | $0.111/hr | |
| 7 | **AssemblyAI** Universal-2 | $0.15/hr | diar +$0.02/hr |
| 8 | **Rev.ai** Reverb | $0.20/hr | diarization default+free |
| 9 | **AssemblyAI** Universal-3 Pro | $0.21/hr | flagship; ~3.1% WER [independent AA] |
| 10 | **ElevenLabs** Scribe v2 | $0.22/hr | **#1 accuracy** [independent AA]; diar (32 spk) + audio-event tags included |
| 11 | **Speechmatics** Std / **Melia $0.129** | $0.129–0.24/hr | per-minute; diar included; 50h/mo free |
| 12 | **Deepgram** Nova-3 prerecorded | $0.26/hr | diar +$0.002/min; $200 free credit |
| 13 | **Azure** batch / **AWS** batch / **OpenAI** gpt-4o-mini | ~$0.18–0.36/hr | mini = $0.18/hr ($0.003/min); AWS/Azure batch ~$0.36 |
| 14 | **OpenAI** whisper-1 / gpt-4o-transcribe | $0.36/hr ($0.006/min) | |
| 15 | **Replicate** | per-compute-sec (~$0.001–0.003+/short run) | **+ billed cold start**; unpredictable for long files |
| 16 | **AWS** streaming | $0.60/hr ($0.01/min) | |
| 17 | **Gladia** Starter | $0.61/hr | Growth ~$0.20/hr at volume |
| 18 | **Google Cloud** | $0.96/hr ($0.016/min) | Dynamic Batch ~$0.24/hr ($0.004/min) |
| 19 | **Azure** real-time | $1.00/hr | batch is far cheaper |
| 20 | **IBM Watson** Plus | $1.20/hr ($0.02/min) | worst accuracy [Picovoice] |
| — | **Rev.ai** human | $119/hr ($1.99/min) | human, not machine |

**Free tiers worth noting:** Deepgram $200 credit; AssemblyAI $50 credit; Speechmatics 50h/mo; Google 60min/mo + $300 GCP credit; AWS 60min/mo×12mo; Azure 5h/mo; IBM 500min/mo; Cloudflare 10k Neurons/day (~3.6h/day); Gladia 10h/mo; ElevenLabs shared credit pool.

---

## 4. Speed deep-dive (fastest-first)

RTFx / ×-real-time. **All are throughput-favorable (large batch, datacenter GPU) — not single-request latency.** Provenance flagged.

| Tier | Engine | Speed | Source |
|---|---|---|---|
| **Local GPU champion** | NVIDIA Parakeet-TDT-0.6B (v2) | **RTFx ~3,380** (bs128); v3 ~842–962× on Together AI | [vendor card + independent AA] |
| | NVIDIA Parakeet-CTC-1.1B | RTFx ~2,793 | [independent Open ASR paper] |
| **Fast cloud (hosted Whisper)** | Groq Whisper-v3 / turbo | **164× / 216–228×** RT | [vendor, AA-validated] |
| | Fireworks (deprecated) | "1hr in <4s" (~900×) | [vendor, unreplicated] |
| | Replicate incredibly-fast-whisper | ~90× RT (150min in ~98s) | [vendor] |
| **Fast closed streaming API** | Deepgram Nova-2/3 | **~477–482×** RT | [independent AA] |
| | AssemblyAI Universal-3 Pro | ~100× RT | [independent AA] |
| | Azure MAI-Transcribe-1.5 | ~260× RT | [independent AA] |
| **Local consumer GPU** | faster-whisper (CTranslate2) | **4× vs openai-whisper** [repo]; ~12× RT large-v3 RTX4070; +2–4× batched | [repo + independent] |
| | whisper.cpp | ~8–10× RT large-v3 GPU/Metal | [independent blog] |
| **Edge / low-latency** | Moonshine (streaming) | up to **43.7× vs Whisper-large-v3**; Medium 107ms vs Whisper-v3 11,286ms | [vendor] |
| | ElevenLabs Scribe v2 Realtime | ~150ms first-partial | [vendor] |
| **Baseline** | vanilla OpenAI Whisper (PyTorch) | ~25–40× RT on datacenter GPU | [vendor framing] |

**Practical "fastest" ranking:** local Parakeet on GPU ≥ Groq-hosted Whisper > Deepgram/AssemblyAI streaming > faster-whisper (single consumer GPU) > whisper.cpp / vanilla Whisper > LLM-based APIs (gpt-4o-transcribe, Gemini) which trade speed for features. **Caveat:** RTFx ≠ latency — Parakeet's ~3,380 RTFx is batch throughput, not low first-word latency; for live UX, latency-tuned streaming (Moonshine, ElevenLabs realtime, Deepgram) matters more.

---

## 5. Recommended TOP-10 to build façades for FIRST

Balanced across (a) free/local, (b) cheap/fast cloud, (c) feature-rich premium cloud. **Easy "first customers"** flagged — these are the lowest-effort adapters that prove the façade's data model.

| # | Engine | Bucket | Why first | Easy first customer? |
|---|---|---|---|---|
| 1 | **faster-whisper** | (a) free/local | The default local workhorse — 4× Whisper, MIT, pip-only, file/bytes/numpy input, clean `(segments, info)` with word timestamps. The reference for the canonical model. | **YES** — simplest local adapter |
| 2 | **OpenAI** (whisper-1 + gpt-4o-transcribe) | (b) cheap cloud | Ubiquitous, sync file-in/JSON-out, verbose_json gives segments+words, now also diarization. **One adapter shape covers Groq + Fireworks too.** | **YES** — trivial sync REST |
| 3 | **Groq** (Whisper v3/turbo) | (b) cheap+fast | **OpenAI-compatible** → near-free to add once #2 exists; cheapest fast cloud ($0.04/hr), 164–228× RT. | **YES** — reuses OpenAI adapter |
| 4 | **Deepgram** Nova-3 | (c) premium | Best-in-class streaming + prerecorded, diarization, word confidence, on-prem option; the canonical "channels→alternatives→words + utterances" shape worth modeling early. | medium |
| 5 | **AssemblyAI** Universal-3 Pro | (c) premium | Exemplary **async submit→poll** model (forces that interface path); top independent WER (~3.1%); rich features; flat `text`+`words`+`utterances`. | medium |
| 6 | **ElevenLabs Scribe v2** | (c) premium | **#1 accuracy** [independent AA]; 32-speaker diarization + audio-event tags (laughter/music) — a unique feature the model should accommodate; cheap ($0.22/hr). | **YES** — sync convert() |
| 7 | **NVIDIA Parakeet** (via NeMo or sherpa-onnx) | (a) free/local | The accuracy+speed frontier (6.05% WER, RTFx ~3,380), CC-BY-4.0, word/seg/char timestamps. Run via **sherpa-onnx** to dodge NeMo's heavy install. | medium (sherpa) / hard (NeMo) |
| 8 | **WhisperX** | (a) free/local | The local **diarization + accurate-alignment** answer (pyannote + wav2vec2 forced align) — exercises the speaker/word-timestamp paths without a cloud bill. | medium (HF token, CUDA) |
| 9 | **Google Cloud STT** (Chirp 2) | (c) premium | Forces the **cloud-storage gate** (`gs://`) + **LRO poll** + per-15s billing — a distinct interface the model must handle; broad language coverage. (Chirp 2, not 3 — Chirp 3 lacks word timestamps.) | hard (GCS, auth) |
| 10 | **Vosk** (or **sherpa-onnx**) | (a) free/local | The **streaming-first, CPU-only, pip-only, $0** option — proves the streaming/partial-results path on-device; ~50MB models, 20+ languages. sherpa-onnx is the more capable sibling (diar+timestamps). | **YES** — pip, no GPU |

**Coverage check:** free/local = faster-whisper, Parakeet, WhisperX, Vosk/sherpa (4–5); cheap/fast cloud = OpenAI, Groq (2); premium cloud = Deepgram, AssemblyAI, ElevenLabs, Google (4). Interface paradigms all exercised: sync (OpenAI/Groq/ElevenLabs/local), async-poll (AssemblyAI/Google), streaming (Deepgram/Vosk), cloud-storage gate (Google), diarization flag/config/separate (Deepgram/Google/OpenAI), local diar (WhisperX).

**Build order suggestion:** start with the **4 easy first customers** (faster-whisper → OpenAI → Groq → ElevenLabs) to lock the canonical model against sync engines + one local + one feature-rich; then add **AssemblyAI** (async-poll) and **Deepgram** (streaming + channels) to stress the interface enum; then **Vosk/sherpa** (on-device streaming), **WhisperX** (local diar/align), **Parakeet** (frontier accuracy), and **Google** (cloud-storage gate) last as the hardest adapters.

---

## 6. Catalog / ledger (everything else worth cataloguing, not implementing first)

**Local / open-source:**
- **OpenAI Whisper (vanilla PyTorch)** — the reference; slower than faster-whisper, so catalog it but implement faster-whisper instead. MIT/Apache-2.0.
- **whisper.cpp** — best for embedded/Apple-Silicon/no-Python deployments; needs CMake build + 3rd-party bindings. MIT.
- **distil-whisper** — English-only, 6× faster than large-v3; great as a speculative-decoding draft or fast EN backend. MIT.
- **NeMo Canary-Qwen-2.5B / Canary-1B-v2** — #1 open accuracy (5.63%) / 25-lang multilingual+translation; heavy NeMo install. CC-BY-4.0.
- **Moonshine** — edge/streaming, 8 languages, MIT, no word timestamps; pick when latency on-device is paramount.
- **wav2vec2 (HF transformers)** — lightest possible baseline; no punctuation; XLSR/MMS variants for many languages. Apache-2.0.
- **Silero STT** — compact CPU models but **CC-BY-NC (non-commercial) trap** and only en/de/es; the project has pivoted to TTS/VAD.
- **SpeechBrain** — research toolkit (ASR+diar+separation+emotion); flexible but not a single tuned product model. Apache-2.0.
- **Kaldi (classic)** — legacy/research; heaviest install (C++ compile), no first-class Python; prefer sherpa-onnx.
- **Ultravox** — audio **LLM**, NOT ASR; catalog for completeness but never select for transcription (generative, no WER, no timestamps).
- **Coqui STT / Mozilla DeepSpeech** — **DEAD** (DeepSpeech archived Jun 2025; Coqui shut Dec 2025); catalog-only, historical.

**Cloud / API:**
- **Speechmatics** — broadest accent/dialect coverage + true on-prem; per-minute; item-level output with `"S1"` speaker labels. Worth implementing if on-prem/dialect coverage matters.
- **Gladia** — Solaria model, 100 languages, async submit-poll + live WS; French vendor; bundled features.
- **AWS Transcribe** — best independent cloud WER (~4.3% Picovoice); S3-gated batch; `items[]` vocabulary; implement if AWS-native.
- **Azure AI Speech** — 140+ languages, on-prem containers, the **most idiosyncratic output** (NBest, 100-ns ticks, four text forms) — a stress test for the model; implement after the easy ones.
- **Rev.ai** — Reverb (non-commercial open weights) + hosted Whisper; diarization free by default; `monologues/elements` vocabulary.
- **Fireworks AI** — **deprecated (2026-06-10)**; do not build on it.
- **Replicate** — hosted Whisper, per-compute-second billing + billed cold start; inconsistent output across its two Whisper models; catalog as a "BYO-model host" pattern.
- **Cloudflare Workers AI** — cheapest cloud (~$0.027/hr), edge, no cold-start, but no diarization/streaming; great for cheap batch.
- **IBM Watson STT** — maintenance mode, worst independent WER (~22%), ~10 languages; on-prem via Cloud Pak; IBM steering new work to watsonx/Granite + Deepgram.

**Also worth cataloguing (surfaced as competitive in independent benchmarks):**
- **Cohere Labs Transcribe** — top of Open ASR Leaderboard (5.42% WER, closed).
- **Zoom Scribe v1** — 5.47% WER [independent Open ASR].
- **IBM Granite Speech 4.0** — 5.52% WER, open weights on watsonx.ai (distinct from Watson STT).
- **Mistral Voxtral** (Small/Mini) — open weights, ~2.8% AA-WER [independent AA]; strong open option.
- **Microsoft MAI-Transcribe-1.5** — 2.4% AA-WER at ~260× RT [independent AA].
- **Google Gemini 2.5/3.x** (audio understanding) — ~2.8% AA-WER but slow (~6.7× RT) and LLM-priced.

---

## 7. References

1. [openai/whisper — GitHub (README, MIT license, transcribe API, model table)](https://github.com/openai/whisper)
2. [openai/whisper-large-v3-turbo — Hugging Face (809M, 4 decoder layers, WER 7.83, RTFx 200, MIT)](https://huggingface.co/openai/whisper-large-v3-turbo)
3. [openai/whisper-large-v3 — Hugging Face (1543.5M, 99 langs, Apache-2.0 tag)](https://huggingface.co/openai/whisper-large-v3)
4. [`large-v3` release · openai/whisper · Discussion #1762](https://github.com/openai/whisper/discussions/1762)
5. [Whisper paper — Robust Speech Recognition via Large-Scale Weak Supervision (arXiv:2212.04356)](https://arxiv.org/abs/2212.04356)
6. [ggml-org/whisper.cpp — GitHub (MIT, GGUF, backends, streaming, tinydiarize)](https://github.com/ggml-org/whisper.cpp)
7. [Whisper.cpp vs faster-whisper 2026 — local STT benchmarks (RTX 4070, M5 Pro)](https://www.promptquorum.com/power-local-llm/local-whisper-stt-comparison-2026)
8. [SYSTRAN/faster-whisper — GitHub (MIT, benchmark tables, batched inference, word timestamps)](https://github.com/SYSTRAN/faster-whisper)
9. [faster-whisper — PyPI](https://pypi.org/project/faster-whisper/)
10. [m-bain/whisperX — GitHub (BSD-2, 70× realtime, wav2vec2 alignment, pyannote diarization)](https://github.com/m-bain/whisperX)
11. [huggingface/distil-whisper — GitHub (6× faster, 50% smaller, within 1% WER)](https://github.com/huggingface/distil-whisper)
12. [distil-whisper/distil-large-v3.5 — Hugging Face (756M, English, WER 7.08/11.39, MIT)](https://huggingface.co/distil-whisper/distil-large-v3.5)
13. [moonshine-ai/moonshine — GitHub (MIT, latency vs Whisper, streaming, numpy API)](https://github.com/moonshine-ai/moonshine)
14. [Flavors of Moonshine: Tiny Specialized ASR Models for Edge Devices (arXiv:2509.02523)](https://arxiv.org/html/2509.02523v1)
15. [nvidia/parakeet-tdt-0.6b-v2 — Hugging Face (CC-BY-4.0, WER 6.05, RTFx ~3,386, timestamps, API)](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2)
16. [nvidia/canary-qwen-2.5b — Hugging Face (SALM, WER 5.63 #1 open, RTFx 418)](https://huggingface.co/nvidia/canary-qwen-2.5b)
17. [nvidia/canary-1b-v2 — Hugging Face (25-language ASR + translation, WER 7.15, RTFx 749)](https://huggingface.co/nvidia/canary-1b-v2)
18. [Open ASR Leaderboard: Towards Reproducible and Transparent Evaluation (arXiv:2510.06961)](https://arxiv.org/html/2510.06961v4)
19. [Open ASR Leaderboard — Hugging Face Space](https://huggingface.co/spaces/hf-audio/open_asr_leaderboard)
20. [Open ASR Leaderboard: Trends and Insights — Hugging Face blog](https://huggingface.co/blog/open-asr-leaderboard)
21. [Wav2Vec2 — Hugging Face Transformers docs](https://huggingface.co/docs/transformers/en/model_doc/wav2vec2)
22. [facebook/wav2vec2-large-960h-lv60-self — Hugging Face (Apache-2.0, LS WER 1.9/3.9)](https://huggingface.co/facebook/wav2vec2-large-960h-lv60-self)
23. [VOSK Offline Speech Recognition API (20+ langs, streaming, speaker ID, 50MB)](https://alphacephei.com/vosk/)
24. [alphacep/vosk-api — GitHub (Apache-2.0, KaldiRecognizer, SetWords word timestamps)](https://github.com/alphacep/vosk-api)
25. [Silero Speech-To-Text Models — PyTorch Hub (en/de/es, CPU)](https://pytorch.org/hub/snakers4_silero-models_stt/)
26. [snakers4/silero-models — GitHub (CC-BY-NC / MIT license split)](https://github.com/snakers4/silero-models)
27. [speechbrain/speechbrain — GitHub (Apache-2.0, ASR+diar+separation, API)](https://github.com/speechbrain/speechbrain)
28. [k2-fsa/sherpa-onnx — GitHub (Apache-2.0, streaming+offline, diarization, CPU, runs Parakeet/Zipformer)](https://github.com/k2-fsa/sherpa-onnx)
29. [kaldi-asr/kaldi — GitHub (Apache-2.0) & kaldi-asr.org](https://github.com/kaldi-asr/kaldi)
30. ["Coqui is shutting down" — coqui-ai/TTS Discussion #3489](https://github.com/coqui-ai/TTS/discussions/3489)
31. [Archive DeepSpeech repo — mozilla/DeepSpeech Issue #3693 (archived Jun 2025)](https://github.com/mozilla/DeepSpeech/issues/3693)
32. [fixie-ai/ultravox — GitHub (audio LLM, MIT + base-LLM license, ~42 langs, no WER)](https://github.com/fixie-ai/ultravox)
33. [Speech to text — OpenAI API guide (models, response_format, 25MB cap, streaming, diarize)](https://developers.openai.com/api/docs/guides/speech-to-text)
34. [Pricing — OpenAI API](https://developers.openai.com/api/docs/pricing)
35. [Introducing next-generation audio models in the API — OpenAI](https://openai.com/index/introducing-our-next-generation-audio-models/)
36. [Groq Pricing](https://groq.com/pricing)
37. [Groq Runs Whisper Large V3 at 164× Real-Time (AA benchmark)](https://groq.com/blog/groq-runs-whisper-large-v3-at-a-164x-speed-factor-according-to-new-artificial-analysis-benchmark)
38. [Speech to Text — GroqDocs](https://console.groq.com/docs/speech-to-text)
39. [Deepgram Pricing](https://deepgram.com/pricing)
40. [Introducing Nova-3 — Deepgram](https://deepgram.com/learn/introducing-nova-3-speech-to-text-api)
41. [Deepgram Docs — Diarization](https://developers.deepgram.com/docs/diarization)
42. [deepgram-python-sdk — GitHub (v7.x)](https://github.com/deepgram/deepgram-python-sdk)
43. [AssemblyAI Pricing](https://www.assemblyai.com/pricing)
44. [Introducing Universal-3 Pro — AssemblyAI blog (Feb 2026)](https://www.assemblyai.com/blog/introducing-universal-3-pro)
45. [Introducing Universal-Streaming — AssemblyAI blog](https://www.assemblyai.com/blog/introducing-universal-streaming)
46. [Get transcript — AssemblyAI Docs (words/utterances ms, speaker labels)](https://www.assemblyai.com/docs/api-reference/transcripts/get)
47. [Transcription / Speech-to-Text — ElevenLabs Docs](https://elevenlabs.io/docs/overview/capabilities/speech-to-text)
48. [Speech-to-Text convert — ElevenLabs API Reference](https://elevenlabs.io/docs/api-reference/speech-to-text/convert)
49. [Introducing Scribe v2 — ElevenLabs blog (Jan 2026)](https://elevenlabs.io/blog/introducing-scribe-v2)
50. [Introducing Scribe v2 Realtime — ElevenLabs blog (~150ms)](https://elevenlabs.io/blog/introducing-scribe-v2-realtime)
51. [ElevenLabs API Pricing](https://elevenlabs.io/pricing/api)
52. [Speechmatics Pricing](https://www.speechmatics.com/pricing)
53. [Batch output (json-v2) — Speechmatics Docs](https://docs.speechmatics.com/speech-to-text/batch/output)
54. [speechmatics-python-sdk — GitHub (modular)](https://github.com/speechmatics/speechmatics-python-sdk)
55. [Gladia Pricing](https://www.gladia.io/pricing)
56. [Pre-recorded workflow — Gladia Docs](https://docs.gladia.io/api-reference/pre-recorded-flow)
57. [Introducing Solaria — Gladia blog](https://www.gladia.io/blog/introducing-solaria-the-first-truly-universal-speech-to-text-model)
58. [Speech-to-Text API Pricing — Google Cloud](https://cloud.google.com/speech-to-text/pricing)
59. [Chirp 3: Enhanced multilingual accuracy — Google Cloud Docs (no word timestamps)](https://docs.cloud.google.com/speech-to-text/docs/models/chirp-3)
60. [Chirp 2 — Google Cloud Docs](https://docs.cloud.google.com/speech-to-text/docs/models/chirp-2)
61. [Transcribe long audio files (batchRecognize) — Google Cloud Docs](https://docs.cloud.google.com/speech-to-text/docs/batch-recognize)
62. [Amazon Transcribe Pricing — AWS](https://aws.amazon.com/transcribe/pricing/)
63. [start_transcription_job — Boto3 documentation](https://docs.aws.amazon.com/boto3/latest/reference/services/transcribe/client/start_transcription_job.html)
64. [Speaker diarization batch output — Amazon Transcribe Docs](https://docs.aws.amazon.com/transcribe/latest/dg/diarization-output-batch.html)
65. [Pricing — Azure AI Speech](https://azure.microsoft.com/en-us/pricing/details/speech/)
66. [Use the fast transcription API — Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/fast-transcription-create)
67. [Display text format (ITN / four forms) — Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/display-text-format)
68. [Rev AI Pricing](https://www.rev.ai/pricing)
69. [Rev AI Asynchronous Speech-to-Text API — docs.rev.ai](https://docs.rev.ai/api/asynchronous/)
70. [Reverb: Open-Source ASR and Diarization from Rev (arXiv:2410.03930)](https://arxiv.org/html/2410.03930v2)
71. [Fireworks Blog — audio transcription launch (Dec 2024)](https://fireworks.ai/blog/audio-transcription-launch)
72. [Fireworks docs — Changelog (audio deprecation 2026-06-10)](https://docs.fireworks.ai/updates/changelog.md)
73. [Replicate — Pricing (GPU per-second rates)](https://replicate.com/pricing)
74. [Replicate — vaibhavs10/incredibly-fast-whisper](https://replicate.com/vaibhavs10/incredibly-fast-whisper)
75. [Cloudflare — Workers AI Pricing (Neurons)](https://developers.cloudflare.com/workers-ai/platform/pricing/)
76. [Cloudflare — @cf/openai/whisper](https://developers.cloudflare.com/workers-ai/models/whisper/)
77. [IBM Cloud Docs — Speech to Text Release Notes](https://cloud.ibm.com/docs/speech-to-text?topic=speech-to-text-release-notes)
78. [IBM Watson STT API docs (Python)](https://cloud.ibm.com/apidocs/speech-to-text?language=python)
79. [Speech to Text (ASR) Providers Leaderboard — Artificial Analysis (independent WER/speed/price)](https://artificialanalysis.ai/speech-to-text)
80. [Picovoice — Open-Source Speech-to-Text Benchmark (independent cloud WER)](https://picovoice.ai/docs/benchmark/stt/)
81. [Best open-source STT model in 2026 benchmarks — Northflank](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks)
82. [Best STT Providers 2026: Independent Benchmarks — Coval](https://www.coval.ai/blog/best-speech-to-text-providers-in-2026-independent-benchmarks-and-how-to-choose/)
