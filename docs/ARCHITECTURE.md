# Architecture

## Purpose

`trysac-sql-migration-lint` is a small, dependency-free Python library that lints PostgreSQL migration files for operations that lock or rewrite tables or lose data, reporting line numbers, rule ids and suppressions.

## Shape

```text
caller code --> sql_migration_lint (public API in __init__.py)
                    |
                    +-- lexer.py   (tokens, comments, statement splitting)
                    +-- linter.py  (lint_sql, suppression directives, finding order)
                    +-- rules.py   (rule catalogue SML001-SML010, per-statement analysis)
                    +-- config.py  (LintConfig, JSON parsing)
                    +-- errors.py  (typed errors with stable codes)
                    +-- __main__.py (command line interface)
```

- **Public API**: the five names in `__all__` of `src/sql_migration_lint/__init__.py` (`ConfigError`, `Finding`, `InputTooLargeError`, `LintConfig`, `MigrationLintError`, `SqlParseError`, `Statement`, `lint_sql`, `split_statements`, `__version__`).
- **Errors**: invalid input raises typed subclasses of `MigrationLintError`, each with a `code`.
- **Side effects**: the library itself performs no I/O. The CLI in `__main__.py` reads files or stdin and writes to stdout and stderr. Logging uses a `NullHandler` only.

## Quality contract

`scripts/check.py` is the single definition of the gates; `fabrica.json` tells the factory and CI how to run it. See [TESTING.md](TESTING.md).

## Decisions

Architecture decisions are recorded in [decisions/](decisions/) as numbered ADRs.
