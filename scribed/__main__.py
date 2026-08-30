# PYTHON_ARGCOMPLETE_OK
"""scribed command-line interface.

Exposes the tools in :mod:`scribed.tools` as subcommands via ``cw``::

    scribed transcribe talk.mp3 --backend faster-whisper --output srt
    scribed backends --capability diarize
    scribed find --local --free --diarization
    scribed info deepgram
    scribed scaffold speechmatics
    scribed validate faster-whisper
    scribed status

The CLI dependency (``cw``) is optional — ``import scribed`` stays dependency-free.
Install it with ``pip install 'scribed[cli]'``.

``cw.mk_parser`` returns a plain :class:`argparse.ArgumentParser`, and ``cw.run``
offers it to ``argcomplete`` before parsing, so the ``PYTHON_ARGCOMPLETE_OK`` marker
above keeps working with no adapter.
"""


def main() -> None:
    try:
        import cw
    except ImportError:  # pragma: no cover - exercised only without the extra
        import sys

        sys.exit(
            "The scribed CLI requires 'cw'. Install it with: pip install 'scribed[cli]'"
        )

    from scribed.tools import _dispatch_funcs

    parser = cw.mk_parser(_dispatch_funcs)
    raise SystemExit(cw.run(parser))


if __name__ == "__main__":
    main()
