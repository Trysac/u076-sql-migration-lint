"""Behavior tests for the public API of sql_migration_lint."""

from __future__ import annotations

import pytest

import sql_migration_lint


def test_normalize_trims_and_lowercases() -> None:
    assert sql_migration_lint.normalize("  Hello World ") == "hello world"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_rejects_blank_input(value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        sql_migration_lint.normalize(value)


def test_version_is_semver() -> None:
    parts = sql_migration_lint.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
