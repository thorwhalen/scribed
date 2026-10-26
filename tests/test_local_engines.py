"""mlx-whisper, parakeet-mlx and WhisperX backends, with fake engine SDKs (offline).

Each SDK is a fake module injected via ``monkeypatch.setitem(sys.modules, ...)``:
no network, no model downloads, no MLX/torch. The fakes record how they were
called, so the tests pin what the adapter sends and how the result lands.
"""

import inspect
import sys
import types

import pytest

pytest.importorskip("numpy")
pytest.importorskip("soundfile")
import numpy as np

import scribed.backends._whisper_common as common
from scribed import registry

SR = 16_000
ONE_SECOND = (0.1 * np.sin(np.linspace(0, 440 * 2 * np.pi, SR))).astype("float32")

WHISPER_RESULT = {
    "text": " hi there",
    "language": "en",
    "segments": [
        {
            "start": 0.0,
            "end": 1.0,
            "text": " hi there",
            "avg_logprob": -0.1,
            "words": [
                {"word": " hi", "start": 0.0, "end": 0.4, "probability": 0.9},
                {"word": " there", "start": 0.4, "end": 1.0, "probability": 0.8},
            ],
        }
    ],
}


def _module(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


@pytest.fixture
def apple_silicon(monkeypatch):
    monkeypatch.setattr(common, "is_apple_silicon", lambda: True)


def _adapter(module):
    from importlib import import_module

    config = import_module(f"scribed.backends.{module}.config").BACKEND_CONFIG
    return import_module(f"scribed.backends.{module}.adapter").Adapter(config)


def test_new_backends_are_registered():
    ids = registry.list_backends()
    assert {"mlx-whisper", "parakeet-mlx", "whisperx"} <= set(ids)


def test_mlx_refuses_off_apple_silicon(monkeypatch):
    monkeypatch.setattr(common, "is_apple_silicon", lambda: False)
    with pytest.raises(RuntimeError, match="Apple Silicon"):
        _adapter("mlx_whisper").transcribe(ONE_SECOND)


def test_mlx_missing_package_points_to_the_extra(monkeypatch, apple_silicon):
    monkeypatch.setitem(sys.modules, "mlx_whisper", None)
    with pytest.raises(ImportError, match=r"scribed\[mlx\]"):
        _adapter("mlx_whisper").transcribe(ONE_SECOND)


def test_mlx_whisper_batch(monkeypatch, apple_silicon):
    calls = []

    def transcribe(audio, **kwargs):
        calls.append((audio, kwargs))
        return WHISPER_RESULT

    monkeypatch.setitem(
        sys.modules, "mlx_whisper", _module("mlx_whisper", transcribe=transcribe)
    )
    t = _adapter("mlx_whisper").transcribe(ONE_SECOND, language="en")
    (seg,) = t.segments
    assert seg.text == "hi there" and [w.text for w in seg.words] == ["hi", "there"]
    assert seg.span.end_ms == 1000 and 0 < seg.confidence < 1
    audio, kwargs = calls[0]
    assert audio.dtype == np.float32 and audio.shape == (SR,)  # decoded, no ffmpeg
    assert kwargs["path_or_hf_repo"] == "mlx-community/whisper-large-v3-turbo"
    assert kwargs["language"] == "en"


def test_mlx_whisper_resolves_bare_sizes(monkeypatch, apple_silicon):
    calls = []
    monkeypatch.setitem(
        sys.modules,
        "mlx_whisper",
        _module(
            "mlx_whisper",
            transcribe=lambda a, **kw: calls.append(kw) or WHISPER_RESULT,
        ),
    )
    _adapter("mlx_whisper").transcribe(ONE_SECOND, model="small")
    assert calls[0]["path_or_hf_repo"] == "mlx-community/whisper-small-mlx"


def test_parakeet_mlx_batch(monkeypatch, apple_silicon):
    loaded, paths = [], []

    class _Model:
        def transcribe(self, path):
            paths.append(path)
            sentence = types.SimpleNamespace(text=" bonjour", start=0.2, end=0.8)
            return types.SimpleNamespace(text=" bonjour", sentences=[sentence])

    def from_pretrained(repo):
        loaded.append(repo)
        return _Model()

    monkeypatch.setitem(
        sys.modules,
        "parakeet_mlx",
        _module("parakeet_mlx", from_pretrained=from_pretrained),
    )
    adapter = _adapter("parakeet_mlx")
    t = adapter.transcribe(ONE_SECOND)
    adapter.transcribe(ONE_SECOND)
    (seg,) = t.segments
    assert seg.text == "bonjour"
    assert (seg.span.start_ms, seg.span.end_ms) == (200, 800)
    assert loaded == ["mlx-community/parakeet-tdt-0.6b-v3"]  # model cached
    assert all(p.endswith(".wav") for p in paths)


@pytest.fixture
def fake_whisperx(monkeypatch):
    log = {"load_model": [], "align": 0, "diarize": []}

    class _Asr:
        def transcribe(self, audio, *, batch_size, language):
            log["audio"] = audio
            return {
                "language": "en",
                "segments": [{"start": 0.0, "end": 1.0, "text": " hi there"}],
            }

    def load_model(model, device, *, compute_type, language):
        log["load_model"].append((model, device, compute_type, language))
        return _Asr()

    def align(segments, model, metadata, audio, device, return_char_alignments):
        log["align"] += 1
        words = [
            {"word": "hi", "start": 0.0, "end": 0.3, "score": 0.9},
            {"word": "there", "start": 0.3, "end": 1.0, "score": 0.7},
        ]
        return {"segments": [{**segments[0], "words": words}]}

    class DiarizationPipeline:
        def __init__(self, **kw):
            log["diarize"].append(kw.get("token", kw.get("use_auth_token")))

        def __call__(self, audio, *, min_speakers, max_speakers):
            return "turns"

    def assign_word_speakers(turns, result):
        for seg in result["segments"]:
            seg["speaker"] = "SPEAKER_00"
        return result

    monkeypatch.setitem(
        sys.modules,
        "whisperx",
        _module(
            "whisperx",
            load_model=load_model,
            load_align_model=lambda language_code, device: ("align-model", {}),
            align=align,
            DiarizationPipeline=DiarizationPipeline,
            assign_word_speakers=assign_word_speakers,
        ),
    )
    monkeypatch.setitem(sys.modules, "torch", None)  # no torch -> cpu
    return log


def test_whisperx_transcribes_and_aligns(fake_whisperx):
    adapter = _adapter("whisperx")
    t = adapter.transcribe(ONE_SECOND)
    adapter.transcribe(ONE_SECOND)
    (seg,) = t.segments
    assert seg.text == "hi there" and [w.text for w in seg.words] == ["hi", "there"]
    assert seg.speaker is None  # diarization off by default
    assert fake_whisperx["load_model"] == [("large-v3", "cpu", "int8", None)]  # cached
    assert fake_whisperx["align"] == 2 and fake_whisperx["diarize"] == []


def test_whisperx_diarizes_with_a_token(monkeypatch, fake_whisperx):
    monkeypatch.setenv("HF_TOKEN", "hf-test")
    t = _adapter("whisperx").transcribe(ONE_SECOND, diarize=True)
    assert t.segments[0].speaker == "SPEAKER_00"
    assert fake_whisperx["diarize"] == ["hf-test"]


@pytest.mark.parametrize("token_arg", ["token", "use_auth_token"])
def test_whisperx_passes_the_token_under_the_installed_spelling(
    monkeypatch, fake_whisperx, token_arg
):
    """whisperx renamed ``use_auth_token`` -> ``token``; the adapter follows the signature."""
    monkeypatch.setenv("HF_TOKEN", "hf-test")
    seen = {}

    class Pipeline:
        def __init__(self, *, device, **kw):
            seen.update(kw)

        def __call__(self, audio, *, min_speakers, max_speakers):
            return "turns"

    Pipeline.__init__.__signature__ = inspect.Signature(
        [
            inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter(token_arg, inspect.Parameter.KEYWORD_ONLY, default=None),
            inspect.Parameter("device", inspect.Parameter.KEYWORD_ONLY, default=None),
        ]
    )
    sys.modules["whisperx"].DiarizationPipeline = Pipeline
    _adapter("whisperx").transcribe(ONE_SECOND, diarize=True)
    assert seen == {token_arg: "hf-test"}


def test_whisper_sized_model_is_a_registry_capability():
    assert set(registry.list_backends("whisper_sized_model")) == {
        "whisper",
        "faster-whisper",
        "mlx-whisper",
        "whispercpp",
        "whisperx",
    }


def test_whisperx_diarize_without_token_is_informative(monkeypatch, fake_whisperx):
    import scribed.credentials as creds

    for var in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(creds, "_soft_load_dotenv", lambda: None)
    with pytest.raises(RuntimeError, match="HF_TOKEN"):
        _adapter("whisperx").transcribe(ONE_SECOND, diarize=True)


def test_whisperx_missing_package_points_to_the_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "whisperx", None)
    with pytest.raises(ImportError, match=r"scribed\[whisperx\]"):
        _adapter("whisperx").transcribe(ONE_SECOND)
