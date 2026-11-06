"""Command line interface: ``python -m sql_migration_lint PATH...``."""

from __future__ import annotations

import argparse
import json
import sys
from typing import TextIO

from .config import MAX_CONFIG_CHARS, LintConfig
from .errors import InputTooLargeError, MigrationLintError
from .lexer import DEFAULT_MAX_INPUT_CHARS
from .linter import Finding, lint_sql

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sql-migration-lint",
        description="Lint PostgreSQL migration files for risky operations.",
    )
    parser.add_argument("paths", nargs="+", metavar="PATH", help="SQL files; '-' reads stdin")
    parser.add_argument("--dialect", choices=("postgres", "generic"), default="postgres")
    parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")
    parser.add_argument("--config", metavar="FILE", default=None, help="JSON configuration file")
    parser.add_argument(
        "--fail-on",
        choices=("error", "warning"),
        default="warning",
        help="lowest severity that makes the exit code 1 (default: warning)",
    )
    return parser


def _read_limited(stream: TextIO, limit: int) -> str:
    """Read at most ``limit + 1`` characters and reject anything longer than ``limit``."""
    text = stream.read(limit + 1)
    if len(text) > limit:
        raise InputTooLargeError(f"input has more than {limit} characters")
    return text


def _read_source(path: str) -> str:
    if path == "-":
        return _read_limited(sys.stdin, DEFAULT_MAX_INPUT_CHARS)
    with open(path, encoding="utf-8", newline="") as handle:
        return _read_limited(handle, DEFAULT_MAX_INPUT_CHARS)


def _load_config(path: str | None) -> LintConfig | None:
    if path is None:
        return None
    with open(path, encoding="utf-8") as handle:
        return LintConfig.from_json(_read_limited(handle, MAX_CONFIG_CHARS))


def _report_error(label: str, exc: Exception) -> None:
    if isinstance(exc, MigrationLintError):
        print(f"{label}: {exc.code}: {exc}", file=sys.stderr)
    else:
        print(f"{label}: {type(exc).__name__}: cannot read input", file=sys.stderr)


def _emit(results: list[tuple[str, Finding]], output_format: str) -> None:
    if output_format == "json":
        payload = [
            {
                "path": path,
                "rule_id": finding.rule_id,
                "severity": finding.severity,
                "line": finding.line,
                "column": finding.column,
                "message": finding.message,
            }
            for path, finding in results
        ]
        print(json.dumps(payload))
        return
    for path, finding in results:
        line = f"{path}:{finding.line}:{finding.column}: {finding.rule_id} {finding.severity}"
        print(f"{line} {finding.message}")


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return the exit code: 0 ok, 1 findings, 2 usage, IO or parse error."""
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_ERROR
    try:
        config = _load_config(args.config)
    except (OSError, ValueError, MigrationLintError) as exc:
        _report_error(args.config, exc)
        return EXIT_ERROR
    results: list[tuple[str, Finding]] = []
    failed = False
    for path in args.paths:
        label = "<stdin>" if path == "-" else path
        try:
            findings = lint_sql(_read_source(path), dialect=args.dialect, config=config)
        except (OSError, ValueError, MigrationLintError) as exc:
            _report_error(label, exc)
            failed = True
            continue
        results.extend((label, finding) for finding in findings)
    _emit(results, args.output_format)
    if failed:
        return EXIT_ERROR
    if any(args.fail_on == "warning" or finding.severity == "error" for _, finding in results):
        return EXIT_FINDINGS
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
