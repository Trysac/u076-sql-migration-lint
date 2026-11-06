# Rules

`sql_migration_lint` reads text only: it tokenizes the script following PostgreSQL documentation
section 4.1 and matches unquoted keywords at the start of a statement or of an `ALTER TABLE`
action. It is not a SQL parser, so strings, quoted identifiers, dollar quotes and comments never
match. Findings are reported at the line and column of the statement's first token and each rule
fires at most once per statement.

| Rule | Severity | Detects |
|---|---|---|
| SML001 | error | `ADD COLUMN ... NOT NULL` without `DEFAULT` (since PostgreSQL 11 a non-volatile `DEFAULT` avoids the rewrite) |
| SML002 | error | `DROP TABLE` or `DROP COLUMN` |
| SML003 | warning | `CREATE INDEX` or `DROP INDEX` without `CONCURRENTLY` |
| SML004 | warning | `ALTER COLUMN ... TYPE` (table rewrite) |
| SML005 | warning | `RENAME` |
| SML006 | warning | `ADD CONSTRAINT` `FOREIGN KEY` or `CHECK` without `NOT VALID` |
| SML007 | error | `TRUNCATE` |
| SML008 | error | `CONCURRENTLY` between `BEGIN` / `START TRANSACTION` and `COMMIT` / `ROLLBACK` |
| SML009 | error | `UPDATE` or `DELETE` without `WHERE` at parenthesis depth 0 |
| SML010 | warning | `ALTER COLUMN ... SET NOT NULL` (full scan under ACCESS EXCLUSIVE) |

The `generic` dialect disables SML003, SML006, SML008 and SML010.

## Suppression and configuration

A line comment `-- migration-lint: ignore=SML002,SML007` on the line directly above a statement
suppresses those rules for that statement. Unknown rule ids raise `ConfigError` with code
`unknown_rule`.

`LintConfig.from_json` reads `{"disabled": [...], "severity_overrides": {...}}`.

## Limits

- Input is limited to 2,000,000 characters (`InputTooLargeError`, code `input_too_large`).
- A single statement is limited to 200,000 tokens; configuration text to 100,000 characters.
- At most 10 findings are reported per statement.
- The CLI reads at most `max_input_chars + 1` characters per file or stdin.

## Command line

```
python -m sql_migration_lint PATH... [--dialect postgres|generic] [--format text|json]
                                     [--config FILE] [--fail-on error|warning]
```

Use `-` as a path to read stdin. Exit codes: 0 ok, 1 findings at or above `--fail-on`, 2 usage,
IO or parse error.
