# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Add the `sql_migration_lint` package: a PostgreSQL-aware lexer, rules SML001-SML010, `lint_sql`, `split_statements`, `LintConfig`, line-comment suppressions and a `python -m sql_migration_lint` CLI.
- Initial project structure from the factory utility template.
