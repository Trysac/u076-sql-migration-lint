# Project record

## Objective

Lint PostgreSQL migration files for operations that lock or rewrite tables or lose data, reporting line numbers, rule ids and suppressions, so that risky migrations are caught in CI or pytest before deploy.

## Scope

- In scope: the public API documented in [README.md](../README.md), the rules SML001-SML010, the PostgreSQL-oriented lexer, the `postgres` and `generic` dialects, the JSON configuration, line-comment suppressions, typed errors, size limits and the command line interface.
- Out of scope: MySQL, database connections, automatic fixes, and any runtime dependency. The library is not a full SQL parser.

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository created from the factory utility template. |

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | 300894 / 107744 |
| Hours (human) | pending measurement |
| Cost (USD) | 0.6916 |

## Factory run u076 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | claude-sonnet-5-5 | yes | 2830 | 101121 | 0 | 4246 | 0.5089 |
| fix-1 | claude-sonnet-5-5 | no | 6 | 865 | 7265 | 41813 | 0.0310 |
| fix-2 | claude-sonnet-5-5 | no | 8 | 787 | 6819 | 56355 | 0.0306 |
| fix-3 | claude-sonnet-5-5 | no | 6 | 480 | 6422 | 40572 | 0.0249 |
| fix-4 | claude-sonnet-5-5 | no | 4 | 323 | 6002 | 24901 | 0.0207 |
| docs | claude-haiku-5-5 | no | 130153 | 4168 | 0 | 0 | 0.0755 |

Total: $0.6916. Prices: Anthropic list prices.
