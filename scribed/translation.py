"""Parameter translation between scribed's normalized kwargs and native engines.

Every backend exposes its own parameter names and scales (``language`` vs
``lang`` vs ``language_code``; ``diarize`` vs ``speaker_labels``;
``timestamps='word'`` vs ``word_timestamps=True``). A backend declares a
``param_map`` in its ``BACKEND_CONFIG`` mapping *normalized* names to native
ones, and :func:`make_kwargs_translator` turns that declaration into a function
that rewrites caller kwargs into the shape the engine wants. This keeps the
facade's vocabulary stable while letting each adapter stay a thin shim.

This mirrors the translation layer used by the sibling ``ocracy`` facade so the
two packages feel the same to read and extend.
"""

import warnings
from typing import Any, Callable, Dict, Optional

__all__ = ["make_kwargs_translator", "validate_param"]


def make_kwargs_translator(
    param_map: Dict[str, Optional[dict]],
    *,
    on_unsupported: str = "warn",
) -> Callable[..., dict]:
    """Create a function that translates normalized kwargs to native kwargs.

    Args:
        param_map: Mapping of ``normalized_name -> native config dict`` where the
            config dict may have:

            - ``native_name`` (str): the backend's parameter name (defaults to
              the normalized name).
            - ``coerce`` (callable): transform the value (e.g. a bool -> the
              string a vendor expects, ``["en"] -> "en"``).
            - ``default`` (Any): value to inject when the caller omits the param.
            - ``None`` as the whole value: the parameter is explicitly *not*
              supported by this backend.
        on_unsupported: What to do with caller params absent from ``param_map``:
            ``"warn"`` (default), ``"raise"``, or ``"ignore"``.

    Returns:
        A ``translate(**kwargs) -> dict`` function.
    """
    supported_names = {k for k, v in param_map.items() if v is not None}

    def translate(**kwargs) -> dict:
        native_kwargs: dict = {}

        for name, value in kwargs.items():
            if name not in param_map:
                if on_unsupported == "raise":
                    raise ValueError(
                        f"Unsupported parameter: {name!r}. "
                        f"Supported: {sorted(supported_names)}"
                    )
                if on_unsupported == "warn":
                    warnings.warn(
                        f"Parameter {name!r} is not supported by this backend "
                        f"and will be ignored.",
                        stacklevel=3,
                    )
                continue

            config = param_map[name]
            if config is None:
                if on_unsupported == "warn":
                    warnings.warn(
                        f"Parameter {name!r} is not supported by this backend.",
                        stacklevel=3,
                    )
                continue

            native_name = config.get("native_name", name)
            coerce = config.get("coerce")
            if coerce is not None:
                value = coerce(value)
            native_kwargs[native_name] = value

        # Apply defaults for params the caller did not provide.
        for name, config in param_map.items():
            if config is None:
                continue
            native_name = config.get("native_name", name)
            if native_name not in native_kwargs and "default" in config:
                native_kwargs[native_name] = config["default"]

        return native_kwargs

    return translate


def validate_param(name: str, value: Any, config: dict) -> Any:
    """Validate a single parameter against ``min``/``max``/``choices`` in config."""
    if "min" in config and value < config["min"]:
        raise ValueError(
            f"Parameter {name!r} value {value} is below minimum {config['min']}"
        )
    if "max" in config and value > config["max"]:
        raise ValueError(
            f"Parameter {name!r} value {value} is above maximum {config['max']}"
        )
    if "choices" in config and value not in config["choices"]:
        raise ValueError(
            f"Parameter {name!r} value {value!r} not in {config['choices']}"
        )
    return value
