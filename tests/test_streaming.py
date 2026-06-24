"""Tests for the real-time (streaming) surface — all model-free and hardware-free.

Exercises VAD utterance segmentation, the synthesized VAD-segmented fallback, the
``transcribe_live`` facade (native vs fallback routing), the ``iter_live`` sync
driver, and import hygiene. No STT model, no network, no audio device: the fakes
in :mod:`scribed.testing` and a synthetic speech/silence waveform stand in.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from contextlib import contextmanager

import pytest

# The streaming surface requires the `audio`/`streaming` extra (numpy + soundfile);
# skip the whole module cleanly if it is not installed rather than erroring on import.
pytest.importorskip("numpy")
pytest.importorskip("soundfile")

import numpy as np

import scribed
from scribed import registry
from scribed.base import Segment, TimeSpan
from scribed.streaming import (
    file_to_stream,
    transcribe_live,
    vad_segmented_stream,
)
from scribed.testing import (
    FakeStreamingTranscriber,
    FakeTranscriber,
    speech_silence_stream,
)
from scribed.vad import EnergyVAD, segment_utterances


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _collect(agen) -> list:
    """Drain an async iterator to a list (on a private event loop)."""

    async def _run():
        return [x async for x in agen]

    return asyncio.run(_run())


@contextmanager
def _registered(backend_id: str, adapter):
    """Temporarily register a fake backend, cleaning up the global registry after."""
    registry.register_backend(
        backend_id, {"name": backend_id, "id": backend_id}, adapter=adapter
    )
    try:
        yield
    finally:
        registry._registry.pop(backend_id, None)
        scribed.services._handles.pop(backend_id, None)


async def _frames(blocks):
    for b in blocks:
        yield np.asarray(b, dtype="float32")


# ---------------------------------------------------------------------------
# VAD
# ---------------------------------------------------------------------------


def test_energy_vad_speech_vs_silence():
    vad = EnergyVAD(threshold=0.01)
    loud = (0.3 * np.sin(np.linspace(0, 50, 1600))).astype("float32")
    quiet = np.zeros(1600, dtype="float32")
    assert vad.is_speech(loud, 16_000) is True
    assert vad.is_speech(quiet, 16_000) is False


def test_segment_utterances_counts_and_offsets():
    sr = 16_000
    block = np.full(int(sr * 0.1), 0.3, dtype="float32")  # 100 ms "speech"
    silence = np.zeros(int(sr * 0.1), dtype="float32")  # 100 ms silence
    # one 300 ms burst, a long gap (>700 ms), then another 300 ms burst
    blocks = [block] * 3 + [silence] * 9 + [block] * 3
    utterances = _collect(
        segment_utterances(_frames(blocks), sample_rate=sr, vad=EnergyVAD())
    )
    assert len(utterances) == 2
    (u0, start0), (u1, start1) = utterances
    assert start0 == 0  # first burst begins at the stream start
    assert start1 > start0  # second burst is later, in absolute ms
    assert u0.dtype == np.float32 and u0.size > 0


# ---------------------------------------------------------------------------
# Audio source
# ---------------------------------------------------------------------------


def test_file_to_stream_chunks_mono():
    sr = 16_000
    wave = np.arange(sr, dtype="float32") / sr  # 1 s ramp
    src = file_to_stream(wave, sample_rate=sr, block_ms=250)
    assert src.sample_rate == sr
    blocks = _collect(src.__aiter__())
    assert len(blocks) == 4  # 1 s / 250 ms
    assert np.allclose(np.concatenate(blocks), wave)


# ---------------------------------------------------------------------------
# Synthesized fallback
# ---------------------------------------------------------------------------


def test_vad_segmented_stream_finalizes_and_offsets():
    engine = FakeTranscriber(texts=["one", "two"])
    src = speech_silence_stream(n_utterances=2)
    segs = _collect(vad_segmented_stream(engine, src, vad=EnergyVAD()))
    assert [s.text for s in segs] == ["one", "two"]
    assert all(s.is_final for s in segs)  # fallback emits finals only
    assert segs[1].span.start_ms > segs[0].span.start_ms  # absolute, monotonic
    assert engine.calls == 2  # one batch decode per utterance


def test_vad_segmented_stream_empty_when_silent():
    engine = FakeTranscriber(texts=["nope"])
    src = file_to_stream(np.zeros(16_000, dtype="float32"), sample_rate=16_000)
    segs = _collect(vad_segmented_stream(engine, src, vad=EnergyVAD()))
    assert segs == [] and engine.calls == 0  # no speech -> no decode


# ---------------------------------------------------------------------------
# transcribe_live facade: fallback vs native routing
# ---------------------------------------------------------------------------


def test_transcribe_live_fallback_route():
    with _registered("fake-batch", FakeTranscriber(texts=["alpha", "beta"])):
        segs = _collect(
            transcribe_live(speech_silence_stream(n_utterances=2), backend="fake-batch")
        )
    assert [s.text for s in segs] == ["alpha", "beta"]
    assert all(s.is_final for s in segs)


def test_transcribe_live_native_route_emits_interims():
    script = (("he", False), ("hello", False), ("hello.", True))
    with _registered("fake-native", FakeStreamingTranscriber(script=script)):
        segs = _collect(
            transcribe_live(
                speech_silence_stream(n_utterances=1), backend="fake-native"
            )
        )
    assert [s.text for s in segs] == ["he", "hello", "hello."]
    assert [s.is_final for s in segs] == [False, False, True]  # interims then final


def test_service_handle_transcribe_live():
    with _registered("fake-svc", FakeTranscriber(texts=["x"])):
        segs = _collect(
            scribed.services["fake-svc"].transcribe_live(
                speech_silence_stream(n_utterances=1)
            )
        )
    assert [s.text for s in segs] == ["x"]


# ---------------------------------------------------------------------------
# iter_live: synchronous driver
# ---------------------------------------------------------------------------


def test_iter_live_sync_driver():
    with _registered("fake-sync", FakeTranscriber(texts=["uno", "dos"])):
        segs = list(
            scribed.iter_live(
                speech_silence_stream(n_utterances=2), backend="fake-sync"
            )
        )
    assert [s.text for s in segs] == ["uno", "dos"]


def test_iter_live_refuses_inside_running_loop():
    async def _inner():
        gen = scribed.iter_live(speech_silence_stream(n_utterances=1), backend="fake-x")
        with pytest.raises(RuntimeError, match="active event loop"):
            list(gen)  # first next() runs the running-loop guard

    asyncio.run(_inner())


# ---------------------------------------------------------------------------
# Spine helpers used by the streaming layer
# ---------------------------------------------------------------------------


def test_segment_offset_to_absolute_time():
    s = Segment("hi", span=TimeSpan(0, 500), is_final=True)
    shifted = s.offset(1400)
    assert shifted.span == TimeSpan(1400, 1900)
    assert s.span == TimeSpan(0, 500)  # original untouched (frozen)


# ---------------------------------------------------------------------------
# Import hygiene: `import scribed` must stay light (no numpy / streaming)
# ---------------------------------------------------------------------------


def test_import_scribed_stays_light():
    code = (
        "import scribed, sys; "
        "assert 'scribed.streaming' not in sys.modules; "
        "assert 'scribed.vad' not in sys.modules; "
        "assert 'numpy' not in sys.modules; "
        "print('ok')"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "ok"
