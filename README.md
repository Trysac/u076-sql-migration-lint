# sql-migration-lint

[![PyPI version](https://img.shields.io/pypi/v/trysac-sql-migration-lint)](https://pypi.org/project/trysac-sql-migration-lint/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-sql-migration-lint)](LICENSE)
[![CI](https://github.com/Trysac/u076-sql-migration-lint/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u076-sql-migration-lint/actions/workflows/ci.yml)

Lint PostgreSQL migration files for operations that lock or rewrite tables or lose data, with line numbers, rule ids and suppressions

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-sql-migration-lint
# or
uv add trysac-sql-migration-lint
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import sql_migration_lint

# normalize() trims surrounding whitespace and lower-cases the text.
print(sql_migration_lint.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    sql_migration_lint.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
