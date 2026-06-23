"""Adapter for the Deepgram (Nova-3) transcription backend.

Maps scribed's normalized request onto Deepgram's pre-recorded REST endpoint and
the returned JSON onto a :class:`scribed.base.Transcript`. The SDK and credential
are resolved lazily so ``import scribed`` stays dependency-free.

When ``utterances=True`` (always, here) Deepgram returns
``results.utterances`` — one diarized speaker turn each, with nested words — and
we build one :class:`~scribed.base.Segment` per utterance (carrying
``speaker=str(utt.speaker)``). When utterances are absent we fall back to a single
segment built from ``channels[0].alternatives[0]``. Deepgram reports times in
**seconds** and confidence already in ``[0, 1]``, so no rescaling is needed.

The Deepgram Python SDK surface has shifted across major versions, so both the
SDK accessor and the response parsing here are deliberately defensive: we try the
v3 ``listen.rest.v("1")`` accessor first, fall back to the older
``listen.prerecorded.v("1")`` one, and read response fields through ``.to_dict()``
(falling back to ``getattr``) so plain dicts and SDK objects are handled alike.
"""

from __future__ import annotations

from scribed.base import Transcript
from scribed.make_backend import BaseTranscriberAdapter, make_segment, make_word


def _get(obj, key, default=None):
    """Read ``key`` from a plain dict or a pydantic-ish SDK object."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _as_dict(resp):
    """Best-effort convert a Deepgram response object to a plain dict.

    The SDK returns rich objects across versions; ``.to_dict()`` gives a stable,
    uniform shape to parse. Falls back to the object itself (handled by ``_get``)
    when no converter is available.
    """
    for attr in ("to_dict", "to_json"):
        fn = getattr(resp, attr, None)
        if callable(fn):
            try:
                out = fn()
            except Exception:  # noqa: BLE001 - fall through to next strategy
                continue
            if isinstance(out, dict):
                return out
            if isinstance(out, str):
                import json

                try:
                    return json.loads(out)
                except Exception:  # noqa: BLE001
                    continue
    return resp


def _speaker_str(speaker):
    """Normalize a Deepgram (int) speaker label to a non-empty ``str`` or ``None``."""
    if speaker is None:
        return None
    s = str(speaker)
    return s or None


class Adapter(BaseTranscriberAdapter):
    """Deepgram (Nova-3) transcription adapter."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from deepgram import DeepgramClient

            from scribed.credentials import resolve_credential

            key = resolve_credential(
                "deepgram",
                env_var=self.config.get("api_env_var") or None,
                required=True,
            )
            self._client = DeepgramClient(key)
        return self._client

    def _call_transcribe_file(self, client, payload, options):
        """Call the SDK's pre-recorded transcribe across known accessor paths.

        v3 exposes ``listen.rest.v("1").transcribe_file``; older versions expose
        ``listen.prerecorded.v("1").transcribe_file``. Try them in turn.
        """
        listen = client.listen
        for accessor in ("rest", "prerecorded"):
            namespace = getattr(listen, accessor, None)
            if namespace is None:
                continue
            try:
                versioned = namespace.v("1")
            except Exception:  # noqa: BLE001 - try the next accessor
                continue
            return versioned.transcribe_file(payload, options)
        raise RuntimeError(
            "Could not find a Deepgram pre-recorded transcribe accessor "
            "(tried client.listen.rest.v('1') and "
            "client.listen.prerecorded.v('1')). The installed deepgram-sdk "
            "version may have an incompatible API surface."
        )

    def _transcribe(
        self, audio, *, model="nova-3", diarize=False, language=None, **native_kwargs
    ) -> Transcript:
        from deepgram import PrerecordedOptions

        from scribed.util import load_audio_bytes

        client = self._get_client()
        audio_bytes = load_audio_bytes(audio)
        payload = {"buffer": audio_bytes}

        options = PrerecordedOptions(
            model=model,
            smart_format=True,
            punctuate=True,
            diarize=bool(diarize),
            utterances=True,
            language=language,
            **native_kwargs,
        )

        resp = self._call_transcribe_file(client, payload, options)
        data = _as_dict(resp)

        results = _get(data, "results")
        channels = _get(results, "channels") or []
        alternative = None
        if channels:
            alternatives = _get(channels[0], "alternatives") or []
            if alternatives:
                alternative = alternatives[0]

        language_out = None
        meta = _get(data, "metadata")
        if meta is not None:
            detected = _get(meta, "detected_language") or _get(meta, "language")
            language_out = detected or language
        else:
            language_out = language

        utterances = _get(results, "utterances")

        if utterances:
            segments = [
                make_segment(
                    _get(u, "transcript") or "",
                    start=_get(u, "start"),
                    end=_get(u, "end"),
                    confidence=_get(u, "confidence"),
                    speaker=_speaker_str(_get(u, "speaker")),
                    words=[
                        make_word(
                            _get(w, "punctuated_word") or _get(w, "word") or "",
                            start=_get(w, "start"),
                            end=_get(w, "end"),
                            confidence=_get(w, "confidence"),
                            speaker=_speaker_str(_get(w, "speaker")),
                        )
                        for w in (_get(u, "words") or [])
                    ],
                )
                for u in utterances
            ]
            text = " ".join(
                (_get(u, "transcript") or "").strip() for u in utterances
            ).strip()
        else:
            transcript_text = _get(alternative, "transcript") or ""
            words = [
                make_word(
                    _get(w, "punctuated_word") or _get(w, "word") or "",
                    start=_get(w, "start"),
                    end=_get(w, "end"),
                    confidence=_get(w, "confidence"),
                    speaker=_speaker_str(_get(w, "speaker")),
                )
                for w in (_get(alternative, "words") or [])
            ]
            segments = [
                make_segment(
                    transcript_text,
                    confidence=_get(alternative, "confidence"),
                    words=words,
                )
            ]
            text = transcript_text

        return Transcript.from_segments(
            segments,
            backend=self.backend_id,
            raw=resp,
            text=text,
            language=language_out,
        )
