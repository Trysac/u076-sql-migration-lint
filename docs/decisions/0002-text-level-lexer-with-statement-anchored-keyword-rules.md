# Text-level lexer with statement-anchored keyword rules

Status: accepted (generated, pending human review)

## Context

Migration reviewers need to catch locking, rewriting and data-losing PostgreSQL operations in CI or pytest without a database connection or a native binary. A full SQL parser is large and brittle, while naive regular expressions are fooled by strings, comments, quoted identifiers and dollar-quoted bodies.

## Decision

Implement a small iterative lexer that follows PostgreSQL documentation section 4.1 (doubled quotes, E strings, quoted identifiers, dollar quotes with a tag, nestable block comments tracked with a counter, parameters, identifiers containing $). Rules match unquoted keywords only, anchored at the start of the statement or of an ALTER TABLE action and aware of parenthesis depth. Statements are scanned lazily with a per-statement token cap and an input size limit, and every failure is a typed MigrationLintError with a stable code.

## Consequences

The linter is dependency-free, deterministic and fast, and quoted text or comments can never trigger a rule. It does not understand the full SQL grammar, so unusual constructs such as WITH ... UPDATE or procedural code are not analyzed, and findings are positioned at the statement start rather than at the offending token. New rules can be added as small functions over the token view without touching the lexer.
