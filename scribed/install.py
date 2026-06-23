"""Install helpers — make it easy (for a human *or* an AI agent) to get a backend running.

Many backends are not just ``pip install`` away: local Whisper needs the *system*
``ffmpeg`` binary, faster-whisper / Whisper download model weights on first use
(with separate CPU/GPU paths), Vosk needs a downloaded model directory, and the
remote backends need a credential rather than a package.

This module turns those realities into structured, OS-aware guidance an agent can
act on:

- :func:`requirements` — what a backend needs (pip extra, system deps for *this*
  OS, GPU notes, model-weight notes, credential env vars), plus whether it's
  already importable. ``Requirements.instructions()`` renders an agent-/human-
  readable plan.
- :func:`check` / :func:`doctor` — is a backend (or every backend) usable right now?
- :func:`install` — optionally run the ``pip install`` for a backend (with
  confirmation) and verify it. System deps and GPU wheels are *surfaced*, not run
  automatically (they need sudo/brew or environment-specific CUDA choices).

The companion ``scribed-install-backend`` skill walks an agent through using these.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

__all__ = [
    "Requirements",
    "requirements",
    "check",
    "available_backends",
    "doctor",
    "install",
]


def _platform() -> str:
    p = sys.platform
    if p.startswith("darwin"):
        return "darwin"
    if p.startswith("linux"):
        return "linux"
    if p.startswith("win"):
        return "windows"
    return p


# ---------------------------------------------------------------------------
# Per-backend install recipes (the tricky knowledge, in one place)
#
# Only fields that differ from the trivial "pip install scribed[<id>]" need an
# entry. ``extra`` is the pyproject extra name when it differs from the backend id.
# ``system`` maps platform -> shell commands. ``gpu`` is an alternative/extra pip
# line for GPU. ``weights`` notes first-run model downloads. ``alt`` suggests a
# lighter/faster backend with comparable results.
# ---------------------------------------------------------------------------
_RECIPES: Dict[str, dict] = {
    "whisper": {  # openai-whisper, the original PyTorch reference implementation
        "extra": "whisper",
        "heavy": True,
        "system": {
            "darwin": ["brew install ffmpeg"],
            "linux": ["sudo apt-get update && sudo apt-get install -y ffmpeg"],
            "windows": [
                "Install ffmpeg: choco install ffmpeg "
                "(or download from https://ffmpeg.org/download.html and add it to PATH)"
            ],
        },
        "system_note": "openai-whisper shells out to the system 'ffmpeg' binary to decode audio.",
        "gpu": "For GPU, install a CUDA build of torch first (https://pytorch.org/get-started/locally/).",
        "weights": "Downloads the Whisper checkpoint on first use (~140 MB base … ~3 GB large-v3), cached under ~/.cache/whisper.",
        "alt": "faster-whisper — same models, ~4x faster and lower memory (CTranslate2), no system ffmpeg needed",
    },
    "faster-whisper": {
        "extra": "faster-whisper",
        "heavy": True,
        "gpu": "For GPU, install CUDA 12 + cuDNN 9 libraries; CTranslate2 picks them up automatically (see the faster-whisper README).",
        "weights": "Downloads the CTranslate2 model from Hugging Face on first use (cached under ~/.cache/huggingface).",
        "notes": [
            "Decodes audio via bundled PyAV — no system ffmpeg required.",
            "Recommended default local engine: fast, accurate, runs on CPU or GPU.",
        ],
    },
    "whispercpp": {
        "extra": "whispercpp",
        "weights": "Downloads a ggml model on first use (tiny … large).",
        "notes": [
            "Pure C/C++ inference via pywhispercpp — light, CPU-friendly, excellent on Apple Silicon."
        ],
    },
    "vosk": {
        "extra": "vosk",
        "weights": "Download a model from https://alphacephei.com/vosk/models and point the backend at it (small models ~50 MB).",
        "notes": [
            "Light, fully offline, supports streaming; lower accuracy than Whisper-class models."
        ],
    },
    # Remote backends — the 'install' is mostly a small client + a credential.
    "openai": {"extra": "openai"},
    "groq": {"extra": "groq"},
    "deepgram": {"extra": "deepgram"},
    "assemblyai": {"extra": "assemblyai"},
    "google-speech": {"extra": "google"},
    "elevenlabs": {"extra": "elevenlabs"},
}


@dataclass
class Requirements:
    """What a backend needs to run — structured for an agent to act on."""

    backend_id: str
    implemented: bool
    available: bool  # importable / usable right now
    is_local: bool
    is_remote: bool
    pip_command: str  # the line to run
    extra: Optional[str] = None
    system: List[str] = field(default_factory=list)  # OS-specific shell commands
    system_note: Optional[str] = None
    gpu: Optional[str] = None
    weights: Optional[str] = None
    heavy: bool = False
    alternative: Optional[str] = None
    credentials: List[str] = field(default_factory=list)  # "ENV_VAR — where to get it"
    notes: List[str] = field(default_factory=list)

    def instructions(self) -> str:
        """An agent-/human-readable, copy-pasteable install plan."""
        if self.available:
            return f"'{self.backend_id}' is already installed and usable. ✓"
        lines = [f"To use the '{self.backend_id}' backend:"]
        n = 1
        if self.system:
            lines.append(f"  {n}. System dependency:")
            for cmd in self.system:
                lines.append(f"       {cmd}")
            if self.system_note:
                lines.append(f"     ({self.system_note})")
            n += 1
        lines.append(f"  {n}. {self.pip_command}")
        if self.gpu:
            lines.append(f"       GPU: {self.gpu}")
        n += 1
        if self.credentials:
            lines.append(f"  {n}. Set credential(s):")
            for c in self.credentials:
                lines.append(f"       {c}")
            n += 1
        if self.weights:
            lines.append(f"  • {self.weights}")
        if self.heavy:
            lines.append(
                "  • Note: large download (deep-learning framework + weights)."
            )
        if self.alternative:
            lines.append(f"  • Faster/lighter alternative: {self.alternative}.")
        for note in self.notes:
            lines.append(f"  • {note}")
        lines.append(
            f"Verify:   python -c \"import scribed; print(scribed.check('{self.backend_id}'))\""
        )
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.instructions()


def _credential_lines(env_var_field: str, provider: str) -> List[str]:
    if not env_var_field:
        return []
    from scribed.credentials import CREDENTIAL_GUIDANCE

    g = CREDENTIAL_GUIDANCE.get(provider)
    link = f"  (get a key: {g['get_key_url']})" if g else ""
    names = (
        env_var_field if isinstance(env_var_field, str) else " / ".join(env_var_field)
    )
    return [f"export {names}{link}"]


def requirements(backend_id: str, *, gpu: bool = False) -> Requirements:
    """Return structured install :class:`Requirements` for ``backend_id``.

    Works for both implemented backends (uses the ``scribed[extra]`` install and
    the recipe) and ledger-only backends (falls back to the ledger's
    ``python_install`` string). Pass ``gpu=True`` to surface GPU wheel guidance.
    """
    from scribed import registry
    from scribed.catalog import catalog

    implemented = backend_id in set(registry.list_backends())
    recipe = _RECIPES.get(backend_id, {})
    record = catalog[backend_id].to_dict() if backend_id in catalog else {}
    cfg = registry.get_config(backend_id) if implemented else {}

    is_local = bool(cfg.get("is_local", record.get("is_local", False)))
    is_remote = bool(cfg.get("is_remote", record.get("is_remote", False)))
    available = check(backend_id) if implemented else False

    # pip command: prefer the scribed extra for implemented backends, else the
    # ledger's python_install string.
    extra = recipe.get("extra") or (backend_id if implemented else None)
    if implemented and extra:
        pip_command = f'pip install "scribed[{extra}]"'
    else:
        ledger_pip = (record.get("python_install") or "").strip()
        pip_command = ledger_pip or f'pip install "scribed[{backend_id}]"'

    system = list(recipe.get("system", {}).get(_platform(), []))
    api_env = cfg.get("api_env_var") or record.get("api_env_var") or ""
    credentials = (
        _credential_lines(api_env, backend_id) if is_remote and api_env else []
    )

    notes = list(recipe.get("notes", []))
    if not implemented:
        notes.append(
            f"scribed does not yet ship a facade for '{backend_id}' — it's in the ledger "
            "only. See the scribed-add-backend skill to wrap it."
        )

    return Requirements(
        backend_id=backend_id,
        implemented=implemented,
        available=available,
        is_local=is_local,
        is_remote=is_remote,
        pip_command=pip_command,
        extra=extra,
        system=system,
        system_note=recipe.get("system_note"),
        gpu=recipe.get("gpu") if (gpu or recipe.get("gpu")) else None,
        weights=recipe.get("weights"),
        heavy=bool(recipe.get("heavy")),
        alternative=recipe.get("alt"),
        credentials=credentials,
        notes=notes,
    )


def check(backend_id: str) -> bool:
    """Is ``backend_id`` importable / usable right now? (no install, no network)."""
    from scribed import registry

    return registry._is_available(backend_id)


def available_backends() -> List[str]:
    """Implemented backends whose dependency is importable right now."""
    from scribed import registry

    return [b for b in registry.list_backends() if registry._is_available(b)]


def doctor() -> dict:
    """Report which implemented backends are usable now and what the rest need.

    Returns ``{"available": [...], "missing": {id: one-line install hint}}``.
    """
    from scribed import registry

    available, missing = [], {}
    for bid in registry.list_backends():
        if registry._is_available(bid):
            available.append(bid)
        else:
            req = requirements(bid)
            hint = req.pip_command
            if req.system:
                hint = f"{req.system[0]} ; {hint}"
            missing[bid] = hint
    return {"available": available, "missing": missing}


def install(
    backend_id: str,
    *,
    yes: bool = False,
    gpu: bool = False,
    verify: bool = True,
    upgrade: bool = False,
) -> dict:
    """Plan (and optionally run) the pip install for a backend.

    With ``yes=False`` (default) this is a **dry run**: it returns the plan
    without changing anything — call ``result['requirements'].instructions()`` to
    show it. With ``yes=True`` it runs ``pip install`` for the backend's extra in
    the current interpreter, then (if ``verify``) checks importability.

    System dependencies and GPU wheels are *surfaced*, never run automatically
    (they need sudo/brew or an environment-specific CUDA choice) — run those
    yourself from ``result['requirements'].system`` / ``.gpu``.
    """
    req = requirements(backend_id, gpu=gpu)
    result = {
        "backend": backend_id,
        "requirements": req,
        "ran": False,
        "available_before": req.available,
    }
    if req.available:
        result["message"] = f"'{backend_id}' is already available — nothing to do."
        return result
    if not req.implemented:
        result["message"] = req.instructions()
        return result
    if not yes:
        result["message"] = (
            "Dry run — pass yes=True to run the pip install.\n" + req.instructions()
        )
        return result

    import subprocess

    target = f"scribed[{req.extra}]" if req.extra else backend_id
    cmd = [sys.executable, "-m", "pip", "install"]
    if upgrade:
        cmd.append("--upgrade")
    cmd.append(target)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    result["ran"] = True
    result["pip_argv"] = cmd
    result["returncode"] = proc.returncode
    result["stdout_tail"] = proc.stdout[-2000:]
    result["stderr_tail"] = proc.stderr[-2000:]
    if verify and proc.returncode == 0:
        # Importability is module-cached; probe in a fresh interpreter.
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import scribed; print(scribed.check('{backend_id}'))",
            ],
            capture_output=True,
            text=True,
        )
        result["available_after"] = probe.stdout.strip() == "True"
    if req.system:
        result["system_todo"] = req.system
    return result
