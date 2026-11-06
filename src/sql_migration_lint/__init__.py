"""Lint PostgreSQL migration files for locking, rewriting and data-losing operations."""

from __future__ import annotations

import logging

from .config import LintConfig
from .errors import ConfigError, InputTooLargeError, MigrationLintError, SqlParseError
from .lexer import Statement, split_statements
from .linter import Finding, lint_sql

__all__ = [
    "ConfigError",
    "Finding",
    "InputTooLargeError",
    "LintConfig",
    "MigrationLintError",
    "SqlParseError",
    "Statement",
    "__version__",
    "lint_sql",
    "split_statements",
]

__version__ = "0.1.0"

logging.getLogger(__name__).addHandler(logging.NullHandler())
