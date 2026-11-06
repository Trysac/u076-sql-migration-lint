# sql-migration-lint

[![PyPI version](https://img.shields.io/pypi/v/trysac-sql-migration-lint)](https://pypi.org/project/trysac-sql-migration-lint/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-sql-migration-lint)](LICENSE)
[![CI](https://github.com/Trysac/u076-sql-migration-lint/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u076-sql-migration-lint/actions/workflows/ci.yml)

Lint PostgreSQL migration files for operations that lock or rewrite tables or lose data, with line numbers, rule ids and suppressions

## Problem

Schema migrations that look harmless in review can take an ACCESS EXCLUSIVE lock on a large table, rewrite it, or drop data in production. Reviewers rarely remember every PostgreSQL locking rule, and the best-known alternative, squawk, ships as a Rust binary. sql-migration-lint is a pure-Python linter that only reads text, so the same patterns can be caught in CI or in pytest before deploy.

## Install

```sh
pip install trysac-sql-migration-lint
# or
uv add trysac-sql-migration-lint
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
from sql_migration_lint import lint_sql

for f in lint_sql("ALTER TABLE t ADD COLUMN c int NOT NULL;"):
    print(f.line, f.column, f.rule_id, f.severity, f.message)
# 1 1 SML001 error ADD COLUMN NOT NULL without DEFAULT fails on populated tables
```

## Public API

- `lint_sql(sql, *, dialect='postgres', config=None) -> list[Finding]`: returns findings sorted by (line, column, rule_id). `dialect` is `'postgres'` or `'generic'`; the generic dialect disables SML003, SML006, SML008 and SML010.
- `split_statements(sql, *, max_input_chars=2_000_000) -> list[Statement]`: splits SQL on semicolons that are outside strings, quoted identifiers, dollar quotes and comments.
- `Finding`: frozen dataclass with `rule_id`, `severity` (`'error'` or `'warning'`), `line`, `column`, `message`.
- `Statement`: frozen dataclass with `text`, `line`, `column`. `text` includes the terminating semicolon.
- `LintConfig(disabled=frozenset(), severity_overrides={})`: frozen dataclass; `LintConfig.from_json(text)` reads `{"disabled": [...], "severity_overrides": {...}}`.
- Errors: `MigrationLintError` with a `code`; subclasses `InputTooLargeError` (`input_too_large`), `SqlParseError` (`parse_error`, with `line`), and `ConfigError` (`unknown_rule` or `invalid_config`). Messages quote at most 200 characters.
- CLI: `python -m sql_migration_lint PATH... [--dialect postgres|generic] [--format text|json] [--config FILE] [--fail-on error|warning]`. Exit codes: 0 no findings, 1 findings, 2 usage, IO or parse error. `-` reads stdin.

Limits: the lexer is not a SQL parser. Input is capped at 2,000,000 characters for `lint_sql` and `split_statements` by default; a statement holds at most 200,000 tokens; at most 10 findings are reported per statement. Suppression uses a `-- migration-lint: ignore=ID[,ID]` line comment placed on the line directly above a statement.

## Why not squawk?

squawk is the best-known PostgreSQL migration linter, but it is a Rust binary. sql-migration-lint has zero dependencies and can be imported directly from pytest.

## Security

See [docs/SECURITY.md](docs/SECURITY.md).

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
