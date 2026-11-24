"""Capture every log record emitted while a case runs (for the PII-in-logs case)."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager


class _Collector(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


@contextmanager
def capture_logs() -> Iterator[list[str]]:
    """Collect every record of every logger at DEBUG while the block runs.

    The root level is lowered for the block and restored after, so the capture sees what an
    operator running at DEBUG would see (the strictest reading of 'searching all logs').
    """
    collector = _Collector()
    root = logging.getLogger()
    previous = root.level
    root.addHandler(collector)
    root.setLevel(logging.DEBUG)
    try:
        yield collector.lines
    finally:
        root.removeHandler(collector)
        root.setLevel(previous)
