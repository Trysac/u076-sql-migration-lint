# Security notes

## Threat model

`trysac-sql-migration-lint` is a pure library: the lint functions perform no I/O. The CLI reads the files or stdin it is given.

Defended:

- **Oversized input**: `lint_sql` and `split_statements` reject input longer than 2,000,000 characters (`split_statements` takes a `max_input_chars` argument); the CLI reads at most that many characters plus one per file or stdin, and configuration files at most 100,000 characters.
- **Pathological statements**: a statement holding more than 200,000 tokens raises an error; findings are capped at 10 per statement; block comments are scanned with a depth counter rather than recursion.
- **Error messages**: they quote at most 200 characters, and non-printable characters in excerpts are replaced by spaces.
- **Malformed configuration**: unknown keys, wrong types, unknown rule ids and invalid severities raise `ConfigError`; invalid JSON raises `ConfigError` instead of propagating `json` errors.
- **Code execution**: the code never uses `eval`, `exec` or pickle.

Not defended:

- The lexer is not a SQL parser. Keyword matching is textual on unquoted tokens, so it can miss risky SQL that is written in unusual ways, and it does not understand semantics such as whether a table is populated.
- The library does not check that a migration is safe to run; findings are advisory.
- Suppression comments (`migration-lint: ignore=`) are trusted as written by the author of the migration.
- Supply chain: the library has no runtime dependencies, but the development toolchain (uv, ruff, mypy, pytest, gitleaks) is not pinned by this document.

## Publishing

Releases are published to PyPI with trusted publishing (OIDC) when available, never with a long-lived token stored in the repository.

To report a vulnerability, see [SECURITY.md](../SECURITY.md).
