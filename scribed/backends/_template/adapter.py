"""Adapter for the Template backend (copy-me).

An adapter turns scribed's normalized request into a native engine call and the
native response into a :class:`scribed.base.Transcript`. Subclassing
:class:`scribed.make_backend.BaseTranscriberAdapter` gives you kwarg translation
for free: implement :meth:`_transcribe`, which receives the audio and the
already-translated *native* kwargs, and return a ``Transcript``.

Three jobs in ``_transcribe``:

1. Get the audio into the form the engine wants
   (``scribed.util.ensure_file_path`` / ``load_audio_bytes`` / ``to_waveform``).
2. Call the engine (import it *inside* ``_transcribe`` so importing scribed stays light).
3. Normalize the output — use ``scribed.make_backend.make_segment`` /
   ``Transcript.from_segments`` / ``Transcript.from_text``, and stash the engine's
   native response in ``raw=``.
"""

from scribed.base import Transcript  # noqa: F401  (commonly needed)
from scribed.make_backend import (  # noqa: F401
    BaseTranscriberAdapter,
    make_segment,
    make_word,
)


class Adapter(BaseTranscriberAdapter):
    """Template adapter — replace the body of ``_transcribe``."""

    def _transcribe(self, audio, **native_kwargs) -> Transcript:
        # 1. import the engine here (lazy)
        # import the_engine
        #
        # 2. normalize the input and call the engine
        # from scribed.util import ensure_file_path, cleanup_temp
        # path, is_temp = ensure_file_path(audio)
        # try:
        #     native = the_engine.transcribe(path, **native_kwargs)
        # finally:
        #     cleanup_temp(path, is_temp)
        #
        # 3. build a normalized result
        # segments = [
        #     make_segment(s.text, start=s.start, end=s.end, confidence=s.conf)
        #     for s in native.segments
        # ]
        # return Transcript.from_segments(segments, backend=self.backend_id, raw=native)
        raise NotImplementedError("Implement _transcribe for this backend.")
