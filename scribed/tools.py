"""Command-line tools for scribed (dispatched via argh in ``__main__``).

Each function here is a thin, CLI-friendly wrapper over the Python API; ``argh``
turns their signatures into subcommands and options. Run ``scribed <command>
--help`` (after ``pip install 'scribed[cli]'``) or ``python -m scribed <command>``.
"""

from __future__ import annotations

import json
from typing import Optional

import scribed

__all__ = [
    "transcribe",
    "backends",
    "info",
    "find",
    "scaffold",
    "validate",
    "requirements",
    "doctor",
    "install",
    "status",
]


def transcribe(
    audio: str,
    *,
    backend: Optional[str] = None,
    language: Optional[str] = None,
    diarize: bool = False,
    output: str = "text",
):
    """Transcribe an audio file/URL and print the result.

    :param audio: Path or http(s) URL to the audio.
    :param backend: Backend id (default: first installed). See ``scribed backends``.
    :param language: Language code hint, e.g. ``en`` (omit to auto-detect).
    :param diarize: Ask the backend to label speakers (if it supports it).
    :param output: ``text`` (default), ``json`` (text + segments), ``srt``, or ``vtt``.
    """
    kwargs = {}
    if language:
        kwargs["language"] = language
    if diarize:
        kwargs["diarize"] = True
    result = scribed.transcribe(audio, backend=backend, **kwargs)

    if output == "json":
        return json.dumps(
            {
                "backend": result.backend,
                "language": result.language,
                "duration": result.duration,
                "text": result.text,
                "segments": [
                    {
                        "start": s.start,
                        "end": s.end,
                        "speaker": s.speaker,
                        "confidence": s.confidence,
                        "text": s.text,
                    }
                    for s in result.segments
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
    if output == "srt":
        return result.srt or result.text
    if output == "vtt":
        return result.vtt or result.text
    return result.text


def backends(*, capability: Optional[str] = None):
    """List the backends scribed can run right now (optionally by capability).

    :param capability: Filter to a capability, e.g. ``diarize``, ``stream``, ``translate``.
    """
    ids = scribed.list_backends(capability)
    lines = []
    for bid in ids:
        info_ = scribed.catalog[bid] if bid in scribed.catalog else None
        where = (
            "+".join(
                w
                for w, on in (("local", info_.is_local), ("remote", info_.is_remote))
                if on
            )
            if info_
            else "?"
        )
        lines.append(f"{bid:18} [{where}]")
    return "\n".join(lines)


def info(backend_id: str):
    """Print a backend's full ledger record as JSON.

    :param backend_id: A ledger id, e.g. ``deepgram`` (see ``scribed find``).
    """
    return json.dumps(
        scribed.catalog[backend_id].to_dict(), indent=2, ensure_ascii=False, default=str
    )


def find(
    *,
    local: bool = False,
    remote: bool = False,
    free: bool = False,
    implemented: bool = False,
    diarization: bool = False,
    streaming: bool = False,
    word_timestamps: bool = False,
    language: Optional[str] = None,
):
    """Filter the ledger and print matching backends (id, where, pricing, best-for).

    Flags compose (AND). Example: ``scribed find --local --free --diarization``.

    :param local: Keep only backends that run locally.
    :param remote: Keep only hosted/remote backends.
    :param free: Keep only free / open-source backends.
    :param implemented: Keep only backends scribed can run today.
    :param diarization: Keep only backends that label speakers.
    :param streaming: Keep only backends that support real-time streaming.
    :param word_timestamps: Keep only backends that emit word-level timestamps.
    :param language: Keep only backends whose languages mention this name/code.
    """
    cat = scribed.catalog
    if local:
        cat = cat.filter(is_local=True)
    if remote:
        cat = cat.filter(is_remote=True)
    if free:
        cat = cat.filter(open_source=True)
    if implemented:
        cat = cat.filter(implemented=True)
    if diarization:
        cat = cat.can("diarization")
    if streaming:
        cat = cat.can("streaming")
    if word_timestamps:
        cat = cat.can("word_timestamps")
    if language:
        cat = cat.supports_language(language)

    lines = []
    for bid in cat.ids:
        i = cat[bid]
        where = "+".join(
            w for w, on in (("local", i.is_local), ("remote", i.is_remote)) if on
        )
        flag = "✓" if i.implemented else " "
        lines.append(
            f"[{flag}] {bid:24} [{where:13}] {i._record.get('pricing_model', '')!s:20} {i._record.get('best_for', '') or ''}"[
                :160
            ]
        )
    header = f"{len(cat)} backend(s) ([✓] = implemented):"
    return header + "\n" + "\n".join(lines)


def scaffold(backend_id: str, *, dest: Optional[str] = None):
    """Generate a new backend package from its ledger entry.

    :param backend_id: The ledger id to scaffold (e.g. ``speechmatics``).
    :param dest: Optional destination directory.
    """
    path = scribed.scaffold_backend(backend_id, dest=dest)
    return (
        f"Scaffolded backend at: {path}\n"
        "Next: fill param_map in config.py and implement adapter.py's _transcribe."
    )


def validate(backend_id: str):
    """Smoke-test a backend adapter end to end and print the report.

    :param backend_id: The backend id to validate (e.g. ``faster-whisper``).
    """
    return json.dumps(
        scribed.validate_adapter(backend_id), indent=2, ensure_ascii=False, default=str
    )


def requirements(backend_id: str, *, gpu: bool = False):
    """Show what a backend needs to run (pip, system deps, GPU, weights, creds).

    :param backend_id: Backend id, e.g. ``whisper``.
    :param gpu: Include GPU-wheel guidance.
    """
    return scribed.requirements(backend_id, gpu=gpu).instructions()


def doctor():
    """Report which backends are usable now, and how to install the rest."""
    rep = scribed.doctor()
    lines = ["Available now:"]
    lines += [f"  ✓ {b}" for b in rep["available"]] or ["  (none)"]
    lines.append("Not installed:")
    for bid, hint in sorted(rep["missing"].items()):
        lines.append(f"  ✗ {bid:24} {hint}")
    return "\n".join(lines)


def install(backend_id: str, *, gpu: bool = False, yes: bool = False):
    """Plan (default) or run (``--yes``) the pip install for a backend.

    Without ``--yes`` it prints the plan and changes nothing. System deps and GPU
    wheels are surfaced, not run automatically.

    :param backend_id: Backend id to install, e.g. ``faster-whisper``.
    :param gpu: Surface GPU-wheel guidance.
    :param yes: Actually run ``pip install`` (otherwise just print the plan).
    """
    res = scribed.install(backend_id, gpu=gpu, yes=yes)
    if res.get("ran"):
        ok = res.get("available_after")
        if ok:
            return f"Installed — '{backend_id}' is ready. ✓"
        return (
            f"pip exit {res['returncode']}; '{backend_id}' still not importable.\n"
            + res["requirements"].instructions()
        )
    return res.get("message") or res["requirements"].instructions()


def status(*, level: str = "all", run_tests: bool = False, names: bool = False):
    """Print an ASR-backend readiness table (levels: all ⊇ implemented ⊇ set_up ⊇ tested).

    :param level: Restrict rows to a level: ``all`` | ``implemented`` | ``set_up`` | ``tested``.
    :param run_tests: Actually transcription-test the set-up backends — makes real API
        calls for set-up remotes (off by default, so a plain ``scribed status`` never bills you).
    :param names: Also print, per level, a comma-separated ``Name (website)`` list.
    """
    info = scribed.backend_info(run_tests=run_tests)
    ids = None if level == "all" else scribed.backend_ids(level, info=info)
    out = [scribed.status_table(ids, info=info)]
    if names:
        from scribed.status import LEVELS as _STATUS_LEVELS

        for lv in _STATUS_LEVELS:
            lids = scribed.backend_ids(lv, info=info)
            out.append(
                f"\n{lv} ({len(lids)}): " + scribed.names_with_sites(lids, info=info)
            )
    return "\n".join(out)


# SSOT list of CLI-dispatchable functions.
_dispatch_funcs = [
    transcribe,
    backends,
    info,
    find,
    scaffold,
    validate,
    requirements,
    doctor,
    install,
    status,
]
