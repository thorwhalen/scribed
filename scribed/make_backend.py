"""Abstraction tools for *building* transcription facades.

Writing a new backend should be mostly declarative. This module supplies the
reusable machinery so an adapter is just "call the engine, return normalized
segments":

- :class:`BaseTranscriberAdapter` — subclass it and implement
  :meth:`~BaseTranscriberAdapter._transcribe`; kwarg translation (via the
  backend's ``param_map``) is handled for you.
- :func:`make_segment` / :func:`make_word` / :func:`normalize_confidence` — build
  normalized :class:`~scribed.base.Segment` / :class:`~scribed.base.Word` from
  whatever shape the engine returned, including confidence-scale normalization.
- :func:`scaffold_backend` — generate a new ``scribed/backends/<id>/`` package
  from the template, pre-filled from the ledger entry. This is the one-command
  way to start a facade for any backend in the catalog.
- :func:`make_test_audio` / :func:`validate_adapter` — smoke-test an adapter end
  to end so you know a new facade actually wires up and returns the right type.

These are the "abstraction tools and skills that know the process" — the
companion :file:`SKILL.md` walks an agent (or human) through using them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, List, Optional, Union

from scribed.base import Segment, TimeSpan, Transcript, Word
from scribed.translation import make_kwargs_translator

__all__ = [
    "BaseTranscriberAdapter",
    "make_segment",
    "make_word",
    "normalize_confidence",
    "scaffold_backend",
    "make_test_audio",
    "validate_adapter",
]

_TEMPLATE_DIR = Path(__file__).parent / "backends" / "_template"


# ---------------------------------------------------------------------------
# Adapter base class
# ---------------------------------------------------------------------------


class BaseTranscriberAdapter:
    """Optional base class for backend adapters.

    Stores the config, builds a kwarg translator from ``config['param_map']``,
    and implements ``transcribe`` as: translate normalized kwargs -> native
    kwargs -> :meth:`_transcribe`. Subclasses implement :meth:`_transcribe` and
    return a :class:`~scribed.base.Transcript`.

    Adapters are not *required* to subclass this — the registry only needs an
    ``Adapter`` class with a ``transcribe(audio, **kwargs)`` method — but doing
    so removes the boilerplate.
    """

    def __init__(self, config: dict):
        self.config = config
        self.backend_id = config.get("id") or config.get("name", "")
        param_map = config.get("param_map")
        self._translate = make_kwargs_translator(param_map) if param_map else None

    #: Override to ``True`` in a backend that talks a live protocol (WebSocket /
    #: streaming recognizer) and implements :meth:`_stream_native`. When ``False``
    #: (the default), live transcription is synthesized from batch ``transcribe``.
    natively_streams: bool = False

    def transcribe(self, audio, **kwargs) -> Transcript:
        native = self._translate(**kwargs) if self._translate else dict(kwargs)
        return self._transcribe(audio, **native)

    def _transcribe(self, audio, **native_kwargs) -> Transcript:  # pragma: no cover
        raise NotImplementedError(
            f"{type(self).__name__}._transcribe is not implemented for "
            f"backend {self.backend_id!r}."
        )

    async def transcribe_live(self, source, *, vad=None, **kwargs):
        """Stream :class:`~scribed.base.Segment`\\ s from a live ``AudioSource``.

        Native-streaming backends set :attr:`natively_streams` and override
        :meth:`_stream_native`; everyone else streams for free here via the
        VAD-segmented batch fallback. ``kwargs`` flow to the per-utterance
        ``transcribe`` (e.g. ``language=``).
        """
        if self.natively_streams:
            async for seg in self._stream_native(source, vad=vad, **kwargs):
                yield seg
        else:
            from scribed.streaming import vad_segmented_stream

            async for seg in vad_segmented_stream(self, source, vad=vad, **kwargs):
                yield seg

    async def _stream_native(self, source, *, vad=None, **kwargs):  # pragma: no cover
        raise NotImplementedError(
            f"{type(self).__name__} set natively_streams=True but did not implement "
            "_stream_native."
        )
        yield  # pragma: no cover - makes this an async generator


# ---------------------------------------------------------------------------
# Result-building helpers
# ---------------------------------------------------------------------------


def normalize_confidence(
    value: Optional[float], *, scale: float = 1.0
) -> Optional[float]:
    """Normalize a raw confidence to ``[0, 1]`` (dividing by ``scale``).

    ``None`` passes through. Use ``scale=100`` for engines that report ``0..100``.
    Engines that report a log-probability should convert before calling this.
    """
    if value is None:
        return None
    v = float(value) / scale if scale and scale != 1.0 else float(value)
    return max(0.0, min(1.0, v))


def _span_from_seconds(
    start: Optional[float], end: Optional[float]
) -> Optional[TimeSpan]:
    """Build a :class:`~scribed.base.TimeSpan` from float seconds, or ``None``.

    Returns ``None`` unless *both* bounds are given — a partially-timed unit is
    treated as untimed (matching the old flat-field behavior).
    """
    if start is None or end is None:
        return None
    return TimeSpan.from_seconds(float(start), float(end))


def make_word(
    text: str,
    *,
    start: Optional[float] = None,
    end: Optional[float] = None,
    confidence: Optional[float] = None,
    conf_scale: float = 1.0,
    speaker: Optional[str] = None,
) -> Word:
    """Build a normalized :class:`~scribed.base.Word`.

    ``start``/``end`` are **seconds** (converted to the millisecond
    :class:`~scribed.base.TimeSpan` internally). ``confidence`` is normalized to
    ``[0, 1]`` via ``conf_scale``.
    """
    return Word(
        text=text,
        span=_span_from_seconds(start, end),
        confidence=normalize_confidence(confidence, scale=conf_scale),
        speaker=speaker,
    )


def make_segment(
    text: str,
    *,
    start: Optional[float] = None,
    end: Optional[float] = None,
    confidence: Optional[float] = None,
    conf_scale: float = 1.0,
    speaker: Optional[str] = None,
    language: Optional[str] = None,
    words: Optional[List[Word]] = None,
    **meta: Any,
) -> Segment:
    """Build a normalized :class:`~scribed.base.Segment`.

    ``start``/``end`` are **seconds** (converted to the millisecond
    :class:`~scribed.base.TimeSpan` internally). ``confidence`` is normalized to
    ``[0, 1]`` via ``conf_scale`` (e.g. ``conf_scale=100`` for percent-scale
    engines).
    """
    return Segment(
        text=text,
        span=_span_from_seconds(start, end),
        confidence=normalize_confidence(confidence, scale=conf_scale),
        speaker=speaker,
        language=language,
        words=tuple(words) if words else (),
        meta=meta,
    )


# ---------------------------------------------------------------------------
# Scaffolding a new backend from the ledger
# ---------------------------------------------------------------------------

_TEMPLATE_LINE = re.compile(
    # A config line tagged for scaffold rewriting. Trailing text after the
    # ``# TEMPLATE`` marker (a usage hint) is allowed and ignored.
    r'^(?P<indent>\s*)"(?P<key>\w+)":\s*(?P<val>.*?),\s*#\s*TEMPLATE\b.*$'
)


def _fmt_value(v: Any) -> str:
    # Booleans first (bool is a subclass of int and of json's number handling).
    if isinstance(v, bool):
        return "True" if v else "False"
    if v is None:
        return '""'
    # json.dumps emits a correctly-escaped, Python-compatible literal — crucial
    # for strings that contain quotes/backslashes, which naive f-string quoting
    # would turn into invalid code.
    return json.dumps(v, ensure_ascii=False)


def _overrides_from_record(backend_id: str, record: Optional[dict]) -> dict:
    """Map a ledger record onto the template's ``# TEMPLATE`` config keys."""
    record = record or {}
    pip_install = (record.get("python_install") or "").strip()
    pip_install = re.sub(r"^\s*pip\s+install\s+", "", pip_install).strip()
    desc = (
        record.get("best_for")
        or (record.get("pros") or [None])[0]
        or record.get("name")
        or backend_id
    )
    return {
        "id": backend_id,
        "name": backend_id,
        "display_name": record.get("name") or record.get("display_name") or backend_id,
        "pip_install": pip_install or "PACKAGE",
        "import_name": backend_id.replace("-", "_"),
        "license": record.get("license") or "unknown",
        "is_local": bool(record.get("is_local", False)),
        "is_remote": bool(record.get("is_remote", False)),
        "description": desc,
    }


def _render_config(template_text: str, overrides: dict) -> str:
    out_lines = []
    for line in template_text.splitlines():
        m = _TEMPLATE_LINE.match(line)
        if m and m.group("key") in overrides:
            key = m.group("key")
            out_lines.append(
                f'{m.group("indent")}"{key}": {_fmt_value(overrides[key])},'
            )
        else:
            out_lines.append(line)
    return "\n".join(out_lines) + ("\n" if template_text.endswith("\n") else "")


def scaffold_backend(
    backend_id: str,
    *,
    dest: Optional[Union[str, Path]] = None,
    overwrite: bool = False,
    ledger: Any = None,
    extra_overrides: Optional[dict] = None,
) -> Path:
    """Create a new ``scribed/backends/<id>/`` package from the template.

    Pre-fills ``config.py`` from the backend's ledger entry (if any) so you only
    have to flesh out ``param_map`` and implement ``adapter.py``'s
    ``_transcribe``.

    Args:
        backend_id: The ledger id (e.g. ``"deepgram"``, ``"faster-whisper"``).
            The on-disk module name uses underscores; the config ``id`` keeps the
            id verbatim.
        dest: Target directory (defaults to ``scribed/backends/<id_underscored>``).
        overwrite: Allow writing into an existing non-empty directory.
        ledger: A :class:`~scribed.catalog.Catalog` to read the record from
            (defaults to the shipped catalog).
        extra_overrides: Extra config-key overrides applied on top of the record.

    Returns:
        The path to the created backend package.
    """
    record = None
    try:
        if ledger is None:
            from scribed.catalog import catalog as ledger
        if backend_id in ledger:
            record = ledger[backend_id].to_dict()
    except Exception:
        record = None

    overrides = _overrides_from_record(backend_id, record)
    if extra_overrides:
        overrides.update(extra_overrides)

    module_name = backend_id.replace("-", "_")
    dest = Path(dest) if dest else (_TEMPLATE_DIR.parent / module_name)
    if dest.exists() and any(dest.iterdir()) and not overwrite:
        raise FileExistsError(
            f"{dest} already exists and is not empty (pass overwrite=True)."
        )
    dest.mkdir(parents=True, exist_ok=True)

    config_text = _render_config(
        (_TEMPLATE_DIR / "config.py").read_text(encoding="utf-8"), overrides
    )
    adapter_text = (_TEMPLATE_DIR / "adapter.py").read_text(encoding="utf-8")
    init_text = f'"""{overrides["display_name"]} backend for scribed."""\n'

    (dest / "__init__.py").write_text(init_text, encoding="utf-8")
    (dest / "config.py").write_text(config_text, encoding="utf-8")
    (dest / "adapter.py").write_text(adapter_text, encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def make_test_audio(
    *,
    duration: float = 1.0,
    sample_rate: int = 16_000,
    freq: float = 440.0,
) -> bytes:
    """Return WAV ``bytes`` of a short sine tone (needs numpy + soundfile).

    A tone carries no speech, so it is a *wiring* smoke test: it proves an
    adapter accepts audio, runs, and returns a :class:`~scribed.base.Transcript`
    of the right shape. To check actual recognition, pass a real speech clip to
    :func:`validate_adapter` via ``audio=`` together with ``expect_text=``.
    """
    from scribed.util import check_import

    np = check_import("numpy", install_hint="numpy", feature="make_test_audio")
    sf = check_import("soundfile", install_hint="soundfile", feature="make_test_audio")
    import io

    t = np.linspace(0.0, duration, int(sample_rate * duration), endpoint=False)
    waveform = (0.2 * np.sin(2.0 * np.pi * freq * t)).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, waveform, sample_rate, format="WAV")
    return buf.getvalue()


def validate_adapter(
    backend_id: str, *, audio: Any = None, expect_text: Optional[str] = None
) -> dict:
    """Smoke-test a backend adapter end to end, returning a report dict.

    Loads the adapter (reporting unavailability instead of raising), runs
    ``transcribe`` on a generated tone (or supplied ``audio``), and checks the
    contract: a :class:`~scribed.base.Transcript` came back. Never raises on a
    *recognition* mismatch — it returns what happened so callers can decide.

    With a tone (no ``audio``), ``ok`` means "ran and returned a Transcript".
    With ``expect_text``, ``ok`` additionally requires the substring to appear.
    """
    from scribed import registry

    report: dict = {
        "backend": backend_id,
        "available": False,
        "ran": False,
        "ok": False,
    }

    try:
        registry.get_config(backend_id)
    except KeyError as e:
        report["error"] = f"not registered: {e}"
        return report

    try:
        adapter = registry.get_backend(backend_id)["adapter"]
    except ImportError as e:
        report["error"] = f"adapter import failed: {e}"
        return report

    # Adapters import their engine lazily, so the class loads even without it.
    # "Available" must reflect whether the engine dependency is actually present.
    report["available"] = registry._is_available(backend_id)
    if not report["available"]:
        cfg = registry.get_config(backend_id)
        report["error"] = (
            f"engine not importable ({cfg.get('import_name')}); "
            f"install with: pip install {cfg.get('pip_install', backend_id)}"
        )
        return report

    if audio is None:
        try:
            audio = make_test_audio()
        except ImportError as e:
            report["error"] = f"cannot generate test audio: {e}"
            return report

    try:
        result = adapter.transcribe(audio)
        report["ran"] = True
    except Exception as e:  # noqa: BLE001 - report any runtime error
        report["error"] = f"{type(e).__name__}: {e}"
        return report

    report["returns_transcript"] = isinstance(result, Transcript)
    report["text"] = getattr(result, "text", None)
    report["n_segments"] = len(getattr(result, "segments", []) or [])
    report["has_timing"] = any(
        s.start is not None for s in getattr(result, "segments", [])
    )
    if expect_text is not None:
        ok = expect_text.lower() in (report["text"] or "").lower()
    else:
        ok = report["returns_transcript"] and report["ran"]
    report["ok"] = bool(report["returns_transcript"] and ok)
    return report
