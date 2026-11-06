"""Typed errors raised by sql_migration_lint.

Every error carries a stable machine-readable ``code``. Messages never include more than a short
excerpt of the offending input and are capped at 200 characters.
"""

from __future__ import annotations

from typing import Literal

ErrorCode = Literal["input_too_large", "parse_error", "unknown_rule", "invalid_config"]

_MAX_MESSAGE_CHARS = 200
_SNIPPET_CHARS = 40


def snippet(text: str, limit: int = _SNIPPET_CHARS) -> str:
    """Return a short, printable excerpt of ``text`` that is safe to embed in a message."""
    head = "".join(ch if ch.isprintable() else " " for ch in text[:limit])
    return head + "..." if len(text) > limit else head


class MigrationLintError(Exception):
    """Base class of every error raised by this library.

    Attributes:
        code: stable machine-readable error code.
    """

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message[:_MAX_MESSAGE_CHARS])
        self.code: ErrorCode = code


class InputTooLargeError(MigrationLintError):
    """The input exceeds a size limit (``code == 'input_too_large'``)."""

    def __init__(self, message: str) -> None:
        super().__init__("input_too_large", message)


class SqlParseError(MigrationLintError):
    """The SQL text cannot be tokenized (``code == 'parse_error'``).

    Attributes:
        line: 1-based line where the offending construct starts.
    """

    def __init__(self, message: str, line: int) -> None:
        super().__init__("parse_error", message)
        self.line = line


class ConfigError(MigrationLintError):
    """A configuration or suppression directive is invalid.

    The code is ``'unknown_rule'`` for an unknown rule id and ``'invalid_config'`` otherwise.
    """

    def __init__(
        self,
        message: str,
        code: Literal["unknown_rule", "invalid_config"] = "invalid_config",
    ) -> None:
        super().__init__(code, message)
