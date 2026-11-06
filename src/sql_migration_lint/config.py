"""Linter configuration."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from .errors import ConfigError, InputTooLargeError, snippet
from .rules import require_known_rule

MAX_CONFIG_CHARS = 100_000

_KEYS = frozenset({"disabled", "severity_overrides"})
_SEVERITIES = frozenset({"error", "warning"})


def _check_rule_id(rule_id: object) -> None:
    if not isinstance(rule_id, str):
        raise ConfigError("rule ids must be strings")
    require_known_rule(rule_id)


@dataclass(frozen=True)
class LintConfig:
    """Immutable linter configuration.

    Attributes:
        disabled: rule ids that never produce findings.
        severity_overrides: maps a rule id to ``'error'`` or ``'warning'``.

    Raises:
        ConfigError: on construction, for unknown rule ids (code ``unknown_rule``) or invalid
            severities (code ``invalid_config``).
    """

    disabled: frozenset[str] = frozenset()
    severity_overrides: Mapping[str, str] = field(default_factory=dict, hash=False)

    def __post_init__(self) -> None:
        disabled = frozenset(self.disabled)
        for rule_id in disabled:
            _check_rule_id(rule_id)
        overrides = dict(self.severity_overrides)
        for rule_id, severity in overrides.items():
            _check_rule_id(rule_id)
            if not isinstance(severity, str) or severity not in _SEVERITIES:
                raise ConfigError(f"invalid severity: {snippet(str(severity))}")
        object.__setattr__(self, "disabled", disabled)
        object.__setattr__(self, "severity_overrides", MappingProxyType(overrides))

    @classmethod
    def from_json(cls, text: str) -> LintConfig:
        """Parse ``{"disabled": [...], "severity_overrides": {...}}``.

        Raises:
            InputTooLargeError: if ``text`` is longer than 100000 characters.
            ConfigError: for malformed JSON, wrong types, unknown keys or rule ids.
        """
        if len(text) > MAX_CONFIG_CHARS:
            raise InputTooLargeError(f"configuration has more than {MAX_CONFIG_CHARS} characters")
        try:
            data = json.loads(text)
        except (ValueError, RecursionError):
            raise ConfigError("configuration is not valid JSON") from None
        if not isinstance(data, dict):
            raise ConfigError("configuration must be a JSON object")
        for key in data:
            if key not in _KEYS:
                raise ConfigError(f"unknown configuration key: {snippet(str(key))}")
        disabled = data.get("disabled", [])
        if not isinstance(disabled, list) or not all(isinstance(item, str) for item in disabled):
            raise ConfigError("'disabled' must be a list of rule ids")
        overrides = data.get("severity_overrides", {})
        if not isinstance(overrides, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in overrides.items()
        ):
            raise ConfigError("'severity_overrides' must map rule ids to severities")
        return cls(disabled=frozenset(disabled), severity_overrides=overrides)
