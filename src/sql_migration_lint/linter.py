"""The ``lint_sql`` entry point."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

from .config import LintConfig
from .errors import ConfigError, snippet
from .lexer import DEFAULT_MAX_INPUT_CHARS, DIRECTIVE_PREFIX, check_size, iter_statements
from .rules import (
    GENERIC_DISABLED,
    MAX_FINDINGS_PER_STATEMENT,
    RULE_MESSAGES,
    RULE_SEVERITIES,
    analyze_statement,
    require_known_rule,
)

logger = logging.getLogger(__name__)

Severity = Literal["error", "warning"]

_IGNORE_PREFIX = "ignore="
_RULE_ID = re.compile(r"[A-Za-z0-9_]+")


@dataclass(frozen=True)
class Finding:
    """One rule violation.

    Attributes:
        rule_id: ``SML001`` .. ``SML010``.
        severity: ``'error'`` or ``'warning'`` (after config overrides).
        line: 1-based line of the statement's first token.
        column: 1-based column of the statement's first token.
        message: short human-readable explanation.
    """

    rule_id: str
    severity: Severity
    line: int
    column: int
    message: str


def parse_directive(text: str) -> list[str] | None:
    """Return the rule ids of a ``migration-lint: ignore=ID[,ID]`` comment, else None."""
    body = text.strip()
    if not body.startswith(DIRECTIVE_PREFIX):
        return None
    rest = body[len(DIRECTIVE_PREFIX) :].strip()
    if not rest.startswith(_IGNORE_PREFIX):
        return None
    parts = [part.strip() for part in rest[len(_IGNORE_PREFIX) :].split(",")]
    if not all(_RULE_ID.fullmatch(part) for part in parts):
        return None
    return parts


def _severity(rule_id: str, config: LintConfig) -> Severity:
    raw = config.severity_overrides.get(rule_id, RULE_SEVERITIES[rule_id])
    return "error" if raw == "error" else "warning"


def lint_sql(
    sql: str,
    *,
    dialect: Literal["postgres", "generic"] = "postgres",
    config: LintConfig | None = None,
) -> list[Finding]:
    """Lint a migration script and return findings sorted by (line, column, rule_id).

    Keywords are matched case-insensitively on unquoted tokens only; strings, quoted identifiers,
    dollar quotes and comments never match. A ``-- migration-lint: ignore=ID[,ID]`` line comment
    on the line directly above a statement suppresses those rules for that statement. The
    ``generic`` dialect disables SML003, SML006, SML008 and SML010.

    Raises:
        InputTooLargeError: if ``sql`` is longer than 2000000 characters.
        SqlParseError: on an unterminated string, identifier, dollar quote or block comment.
        ConfigError: for an unknown dialect or an ``ignore=`` directive naming an unknown rule.
    """
    if dialect not in ("postgres", "generic"):
        raise ConfigError(f"unknown dialect: {snippet(str(dialect))}")
    active = config if config is not None else LintConfig()
    check_size(sql, DEFAULT_MAX_INPUT_CHARS)
    directives: dict[int, set[str]] = {}

    def on_comment(line: int, text: str) -> None:
        rule_ids = parse_directive(text)
        if rule_ids is None:
            return
        for rule_id in rule_ids:
            require_known_rule(rule_id)
        directives.setdefault(line, set()).update(rule_ids)

    off = set(active.disabled)
    if dialect == "generic":
        off |= GENERIC_DISABLED
    findings: list[Finding] = []
    in_tx = False
    count = 0
    for statement, tokens in iter_statements(sql, on_comment):
        count += 1
        hits, in_tx = analyze_statement(tokens, in_tx)
        ignored = directives.get(statement.line - 1, set())
        for rule_id in hits[:MAX_FINDINGS_PER_STATEMENT]:
            if rule_id in off or rule_id in ignored:
                continue
            findings.append(
                Finding(
                    rule_id,
                    _severity(rule_id, active),
                    statement.line,
                    statement.column,
                    RULE_MESSAGES[rule_id],
                )
            )
    findings.sort(key=lambda finding: (finding.line, finding.column, finding.rule_id))
    logger.debug("linted %d statements, %d findings", count, len(findings))
    return findings
