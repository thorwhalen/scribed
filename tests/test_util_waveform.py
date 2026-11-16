"""Tests for scribed.util.to_waveform: ffmpeg fallback for compressed formats."""

import pytest

pytest.importorskip("numpy")
pytest.importorskip("soundfile")
import numpy as np

_SR = 16_000
_ONE_SECOND = (0.1 * np.sin(np.linspace(0, 440 * 2 * np.pi, _SR))).astype("float32")


# --- to_waveform falls back to ffmpeg for formats libsndfile cannot read (#15) ---


def test_to_waveform_decodes_m4a_via_ffmpeg(tmp_path):
    import shutil
    import subprocess

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg not installed")
    import soundfile as sf

    from scribed.util import to_waveform

    wav = tmp_path / "tone.wav"
    sf.write(str(wav), _ONE_SECOND, _SR)
    m4a = tmp_path / "tone.m4a"
    cmd = [ffmpeg, "-y", "-i", str(wav), "-c:a", "aac", str(m4a)]
    subprocess.run(cmd, check=True, capture_output=True)
    for source in (str(m4a), m4a.read_bytes()):  # a path, and raw bytes
        data, sr = to_waveform(source)
        assert data.ndim == 1 and sr == _SR
        assert abs(len(data) - _SR) < 0.1 * _SR


def test_requirements_mention_ffmpeg():
    from scribed.install import requirements

    assert any("ffmpeg" in n for n in requirements("mlx-whisper").notes)


def test_requirements_ffmpeg_note_only_for_waveform_backends():
    from scribed.install import requirements

    assert not any("ffmpeg" in n for n in requirements("openai").notes)


def test_missing_ffmpeg_is_a_clear_error(tmp_path, monkeypatch):
    import shutil

    from scribed.util import to_waveform

    bad = tmp_path / "x.m4a"
    bad.write_bytes(b"not audio")
    monkeypatch.setattr(shutil, "which", lambda *_: None)
    with pytest.raises(RuntimeError, match="ffmpeg"):
        to_waveform(str(bad))


def test_missing_file_is_file_not_found(tmp_path):
    from scribed.util import to_waveform

    with pytest.raises(FileNotFoundError):
        to_waveform(str(tmp_path / "nope.m4a"))


def test_undecodable_file_leaks_no_temp_wav(tmp_path):
    import glob
    import shutil
    import tempfile

    from scribed.util import to_waveform

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    bad = tmp_path / "x.m4a"
    bad.write_bytes(b"not audio")
    before = set(glob.glob(tempfile.gettempdir() + "/*.wav"))
    with pytest.raises(RuntimeError, match="ffmpeg could not decode"):
        to_waveform(str(bad))
    assert set(glob.glob(tempfile.gettempdir() + "/*.wav")) == before
