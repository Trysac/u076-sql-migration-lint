# Testing

## Running

```sh
uv run pytest --cov=sql_migration_lint   # tests with coverage report
uv run python scripts/check.py      # every gate, as CI and the factory run it
```

## Policy

- Branch coverage of `src/sql_migration_lint` must stay at or above 80 %; the gate fails below it.
- Tests exercise the public API (`import sql_migration_lint`) and assert observable effects: return values, raised exceptions and their messages.
- Each bug fix starts with a failing test that reproduces it.
- Tests are deterministic: no network, no wall clock, no dependence on test order.

## Layout

`tests/test_<module>.py` mirrors each public module. Shared fixtures go in `tests/conftest.py`. The test files present in the repository are not described in detail here; the acceptance criteria in the specification (empty and comment-only files, missing final semicolon, lexer edge cases, suppressions, size limits and the CLI exit codes) define what the tests are expected to cover.
