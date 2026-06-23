# PYTHON_ARGCOMPLETE_OK
"""scribed command-line interface.

Exposes the tools in :mod:`scribed.tools` as subcommands via ``argh``::

    scribed transcribe talk.mp3 --backend faster-whisper --output srt
    scribed backends --capability diarize
    scribed find --local --free --diarization
    scribed info deepgram
    scribed scaffold speechmatics
    scribed validate faster-whisper
    scribed status

The CLI dependency (``argh``) is optional — ``import scribed`` stays dependency-free.
Install it with ``pip install 'scribed[cli]'``.
"""


def main() -> None:
    try:
        import argh
    except ImportError:  # pragma: no cover - exercised only without the extra
        import sys

        sys.exit(
            "The scribed CLI requires 'argh'. Install it with: pip install 'scribed[cli]'"
        )

    from scribed.tools import _dispatch_funcs

    parser = argh.ArghParser()
    parser.add_commands(_dispatch_funcs)

    try:  # optional shell tab-completion
        import argcomplete

        argcomplete.autocomplete(parser)
    except ImportError:
        pass

    parser.dispatch()


if __name__ == "__main__":
    main()
