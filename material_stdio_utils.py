"""Helpers for forcing UTF-8 stdio in subprocess protocol entrypoints."""

from __future__ import annotations

import io
import sys
from typing import TextIO


def ensure_utf8_text_stream(stream: TextIO) -> TextIO:
    """Return a UTF-8 text stream wrapper for subprocess JSON protocols."""

    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="strict")
        return stream

    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        return stream

    return io.TextIOWrapper(
        buffer,
        encoding="utf-8",
        errors="strict",
        write_through=True,
        line_buffering=True,
    )


def configure_utf8_stdio() -> None:
    """Force stdout/stderr to UTF-8 for worker/service JSON messages."""

    sys.stdout = ensure_utf8_text_stream(sys.stdout)
    sys.stderr = ensure_utf8_text_stream(sys.stderr)
