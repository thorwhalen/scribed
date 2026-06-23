"""Implemented speech-to-text backends.

Each real backend is a subpackage with a ``config.py`` (``BACKEND_CONFIG``) and an
``adapter.py`` (``Adapter`` with a ``transcribe`` method). The registry
(:mod:`scribed.registry`) discovers them automatically. Subpackages whose name
starts with ``_`` (e.g. :mod:`scribed.backends._template`) are scaffolding
helpers, not real backends, and are skipped by discovery.

To add a backend, scaffold one from the template::

    from scribed.make_backend import scaffold_backend
    scaffold_backend("speechmatics")   # creates scribed/backends/speechmatics/ from the template
"""
