"""Tests for the public API of sql_migration_lint."""

from __future__ import annotations

import dataclasses
import logging

import pytest

from sql_migration_lint import (
    ConfigError,
    Finding,
    InputTooLargeError,
    LintConfig,
    MigrationLintError,
    SqlParseError,
    Statement,
    __version__,
    lint_sql,
    split_statements,
)
from sql_migration_lint.rules import MAX_FINDINGS_PER_STATEMENT

SPLIT_SQL = "SELECT ';';\nSELECT \"a;b\";\nCREATE FUNCTION f() RETURNS int AS $f$ SELECT 1; $f$ LANGUAGE sql;\n-- x; y\n/* /* ; */ */ SELECT 2;"  # noqa: E501
ADJACENT = "SELECT 'DROP TABLE t'; -- DROP TABLE t\nCREATE TABLE \"drop table\" (id int);"

RULE_CASES = [
    ("ALTER TABLE t ADD COLUMN c int;", []),
    ("ALTER TABLE t ADD c int NOT NULL;", ["SML001"]),
    ("ALTER TABLE t ADD COLUMN IF NOT EXISTS c int;", []),
    ("ALTER TABLE t ADD COLUMN c int CHECK (c IS NOT NULL);", []),
    ("ALTER TABLE t ADD COLUMN c int NOT NULL DEFAULT'x';", []),
    ("ALTER TABLE t ADD COLUMN c int NOT NULL/*x*/DEFAULT 0;", []),
    ("ALTER TABLE ONLY public.t ADD COLUMN c int NOT NULL;", ["SML001"]),
    ("ALTER TABLE IF EXISTS t ADD COLUMN c int NOT NULL;", ["SML001"]),
    ('ALTER TABLE "my t" ADD COLUMN c int NOT NULL;', ["SML001"]),
    ("ALTER TABLE t ADD COLUMN c numeric(10,2) NOT NULL, ADD COLUMN d int;", ["SML001"]),
    ("DROP TABLE t;", ["SML002"]),
    ("DROP TABLE t1;", ["SML002"]),
    ("drop table t;", ["SML002"]),
    ("DrOp TaBlE t;", ["SML002"]),
    ("DROP TABLE IF EXISTS t;", ["SML002"]),
    ("ALTER TABLE t DROP COLUMN c;", ["SML002"]),
    ("ALTER TABLE t DROP c;", ["SML002"]),
    ("ALTER TABLE t DROP CONSTRAINT c;", []),
    ("DROP INDEX i;", ["SML003"]),
    ("DROP INDEX CONCURRENTLY i;", []),
    ("CREATE UNIQUE INDEX i ON t (c);", ["SML003"]),
    ("CREATE INDEX CONCURRENTLY i ON t (c);", []),
    ("CREATE TABLE t (id int);", []),
    ("ALTER TABLE t ALTER COLUMN c TYPE bigint;", ["SML004"]),
    ("ALTER TABLE t ALTER c SET DATA TYPE bigint;", ["SML004"]),
    ("ALTER TABLE t ALTER COLUMN type TYPE int;", ["SML004"]),
    ("ALTER TABLE t ALTER COLUMN c SET DEFAULT 1;", []),
    ("ALTER TABLE t RENAME TO u;", ["SML005"]),
    ("ALTER TABLE t RENAME COLUMN a TO b;", ["SML005"]),
    ("ALTER INDEX i RENAME TO j;", ["SML005"]),
    ("ALTER TABLE t ADD COLUMN rename int;", []),
    ("ALTER TABLE t ADD CONSTRAINT fk FOREIGN KEY (a) REFERENCES u (id);", ["SML006"]),
    ("ALTER TABLE t ADD CONSTRAINT fk FOREIGN KEY (a) REFERENCES u (id) NOT VALID;", []),
    ("ALTER TABLE t ADD FOREIGN KEY (a) REFERENCES u (id);", ["SML006"]),
    ("ALTER TABLE t ADD CONSTRAINT ck CHECK (a > 0);", ["SML006"]),
    ("ALTER TABLE t ADD CONSTRAINT ck CHECK (a > 0) NOT VALID;", []),
    ("ALTER TABLE t ADD PRIMARY KEY (a);", []),
    ("TRUNCATE t;", ["SML007"]),
    ("UPDATE t SET a = 1;", ["SML009"]),
    ("DELETE FROM t;", ["SML009"]),
    ("DELETE FROM t WHERE id = 1;", []),
    ("UPDATE t SET a = (SELECT 1 WHERE true);", ["SML009"]),
    ("ALTER TABLE t ALTER COLUMN c SET NOT NULL;", ["SML010"]),
    ("ALTER TABLE t DROP COLUMN a, DROP COLUMN b;", ["SML002"]),
    ("ALTER TABLE t ADD COLUMN a int NOT NULL, DROP COLUMN b;", ["SML001", "SML002"]),
    ("SELECT 1DROP TABLE t;", []),
    ("ALTER TABLE t ALTER COLUMN c \u017fET NOT NULL;", []),
]


def ids(sql: str, dialect: str = "postgres") -> list[str]:
    return [finding.rule_id for finding in lint_sql(sql, dialect=dialect)]


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_logger_has_only_a_null_handler() -> None:
    handlers = logging.getLogger("sql_migration_lint").handlers
    assert any(isinstance(handler, logging.NullHandler) for handler in handlers)


def test_add_column_not_null_without_default() -> None:
    findings = lint_sql("ALTER TABLE t ADD COLUMN c int NOT NULL;")
    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_id == "SML001"
    assert finding.severity == "error"
    assert finding.line == 1
    assert finding.column == 1
    assert lint_sql("ALTER TABLE t ADD COLUMN c int NOT NULL DEFAULT 0;") == []


@pytest.mark.parametrize(("sql", "expected"), RULE_CASES)
def test_rule_table(sql: str, expected: list[str]) -> None:
    assert ids(sql) == expected


def test_many_rules_in_one_statement() -> None:
    sql = (
        "ALTER TABLE t ADD COLUMN a int NOT NULL, DROP COLUMN b, ALTER COLUMN c TYPE int, "
        "ALTER COLUMN d SET NOT NULL, RENAME TO u, ADD CONSTRAINT ck CHECK (a > 0);"
    )
    expected = ["SML001", "SML002", "SML004", "SML005", "SML006", "SML010"]
    assert ids(sql) == expected
    assert len(expected) <= MAX_FINDINGS_PER_STATEMENT == 10


def test_dialect_postgres_and_generic() -> None:
    findings = lint_sql("CREATE INDEX i ON t (c);", dialect="postgres")
    assert [f.rule_id for f in findings] == ["SML003"]
    assert findings[0].severity == "warning"
    assert lint_sql("CREATE INDEX i ON t (c);", dialect="generic") == []
    assert [f.rule_id for f in lint_sql("CREATE INDEX i ON t (c);")] == ["SML003"]


def test_generic_disables_four_rules_but_keeps_the_rest() -> None:
    assert ids("ALTER TABLE t ADD CONSTRAINT ck CHECK (a > 0);", "generic") == []
    assert ids("ALTER TABLE t ALTER COLUMN c SET NOT NULL;", "generic") == []
    assert ids("BEGIN; CREATE INDEX CONCURRENTLY i ON t (c); COMMIT;", "generic") == []
    assert ids("ALTER TABLE t ADD COLUMN c int NOT NULL;", "generic") == ["SML001"]


def test_unknown_dialect_is_rejected() -> None:
    with pytest.raises(ConfigError) as info:
        lint_sql("SELECT 1;", dialect="mysql")  # type: ignore[arg-type]
    assert info.value.code == "invalid_config"


def test_concurrently_inside_transaction() -> None:
    assert [
        f.rule_id for f in lint_sql("BEGIN; CREATE INDEX CONCURRENTLY i ON t (c); COMMIT;")
    ] == ["SML008"]


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("COMMIT; CREATE INDEX CONCURRENTLY i ON t (c);", []),
        ("BEGIN; SELECT 1; COMMIT; CREATE INDEX CONCURRENTLY i ON t (c);", []),
        ("BEGIN; ROLLBACK; DROP INDEX CONCURRENTLY i;", []),
        ("START TRANSACTION; DROP INDEX CONCURRENTLY i; ROLLBACK;", ["SML008"]),
        ("BEGIN; SAVEPOINT s; ROLLBACK TO s; CREATE INDEX CONCURRENTLY i ON t (c);", ["SML008"]),
        ("BEGIN; ROLLBACK PREPARED 'x'; CREATE INDEX CONCURRENTLY i ON t (c);", ["SML008"]),
        ("BEGIN; ALTER TABLE t DETACH PARTITION p CONCURRENTLY;", ["SML008"]),
        ("BEGIN; SELECT 'CONCURRENTLY';", []),
        ("BEGIN; CREATE TABLE t (concurrently int);", []),
    ],
)
def test_transaction_tracking(sql: str, expected: list[str]) -> None:
    assert ids(sql) == expected


def test_split_statements_acceptance() -> None:
    statements = split_statements(SPLIT_SQL)
    assert len(statements) == 4
    assert [s.line for s in statements] == [1, 2, 3, 5]


def test_statement_fields() -> None:
    assert split_statements("  SELECT 1;") == [Statement("SELECT 1;", 1, 3)]
    assert split_statements("SELECT 1") == [Statement("SELECT 1", 1, 1)]


def test_empty_and_comment_only_inputs() -> None:
    for sql in ("", "   \n", "-- just a comment\n", "/* c */", ";;", "-- a\n/* b */ ;"):
        assert split_statements(sql) == []
        assert lint_sql(sql) == []


def test_no_final_semicolon() -> None:
    findings = lint_sql("DROP TABLE t")
    assert [f.rule_id for f in findings] == ["SML002"]


def test_line_and_column_tracking() -> None:
    assert split_statements("/* c */ SELECT 1;")[0].column == 9
    assert (
        split_statements("/* a\nb */ SELECT 1;")[0].line,
        split_statements("/* a\nb */ SELECT 1;")[0].column,
    ) == (2, 6)
    crlf = split_statements("SELECT 1;\r\nSELECT 2;\r\n\r\nSELECT 3;")
    assert [s.line for s in crlf] == [1, 2, 4]
    assert [s.column for s in crlf] == [1, 1, 1]
    assert [s.line for s in split_statements("SELECT 1;\rSELECT 2;")] == [1, 2]
    assert split_statements("SELECT 'a\nb'; SELECT 2;")[1].line == 2


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 'it''s; ok'; SELECT 2;",
        "SELECT E'a\\'b; c'; SELECT 2;",
        "SELECT e'a\\'b;'; SELECT 2;",
        "SELECT xe'a\\'; SELECT 2;",
        "SELECT 'a\\'; SELECT 2;",
        'SELECT "a""b;c"; SELECT 2;',
        "SELECT $$ a; b $$; SELECT 2;",
        "SELECT $a$ $b$ ; $b$ $a$; SELECT 2;",
        "SELECT $a1$ x; $a1$; SELECT 2;",
        "SELECT $1; SELECT $2;",
        "SELECT $1a$ x; SELECT 2;",
        "SELECT a$b$; SELECT 2;",
        "SELECT 1; /*/ ; */ SELECT 2;",
        "SELECT 1 -- ; \n; SELECT 2;",
    ],
)
def test_lexer_keeps_quoted_semicolons_together(sql: str) -> None:
    assert len(split_statements(sql)) == 2


def test_deeply_nested_comments_are_iterative() -> None:
    depth = 50_000
    assert split_statements("/*" * depth + "*/" * depth + " SELECT 1;") == [
        Statement("SELECT 1;", 1, depth * 4 + 2)
    ]


def test_many_parentheses() -> None:
    assert lint_sql("SELECT " + "(" * 50_000 + ")" * 50_000 + ";") == []


def test_many_statements() -> None:
    assert len(split_statements("SELECT 1;\n" * 20_000)) == 20_000


@pytest.mark.parametrize(
    ("sql", "line"),
    [
        ("SELECT 'abc", 1),
        ('SELECT "abc', 1),
        ("SELECT 1;\nSELECT /* x", 2),
        ("SELECT E'abc\\'", 1),
        ("SELECT 1;\n\n$$ x", 3),
        ("/* /* */", 1),
        ("/*" * 50_000, 1),
    ],
)
def test_unterminated_constructs(sql: str, line: int) -> None:
    with pytest.raises(SqlParseError) as info:
        split_statements(sql)
    assert info.value.code == "parse_error"
    assert info.value.line == line
    assert len(str(info.value)) <= 200


def test_unterminated_dollar_quote_acceptance() -> None:
    with pytest.raises(SqlParseError) as info:
        split_statements("SELECT 1;\nSELECT 2;\nSELECT $a$ x")
    err = info.value
    assert err.code == "parse_error"
    assert err.line == 3
    assert len(str(err)) <= 200
    assert isinstance(err, MigrationLintError)


def test_error_messages_quote_little_input() -> None:
    with pytest.raises(SqlParseError) as info:
        split_statements("'" + "a" * 1000)
    assert len(str(info.value)) <= 200
    assert "a" * 100 not in str(info.value)
    assert len(str(MigrationLintError("parse_error", "x" * 500))) == 200


def test_input_size_limit() -> None:
    """Input over max_input_chars raises InputTooLargeError before tokenizing."""
    with pytest.raises(InputTooLargeError) as info:
        split_statements("x" * 11, max_input_chars=10)
    assert info.value.code == "input_too_large"
    assert split_statements("x" * 10, max_input_chars=10) == [Statement("x" * 10, 1, 1)]


def test_size_limit_is_checked_before_tokenizing() -> None:
    with pytest.raises(InputTooLargeError):
        split_statements("'" * 11, max_input_chars=10)
    with pytest.raises(InputTooLargeError):
        lint_sql("x" * 2_000_001)


@pytest.mark.parametrize("limit", [-1, True, "10"])
def test_invalid_limit(limit: object) -> None:
    with pytest.raises(ConfigError) as info:
        split_statements("x", max_input_chars=limit)  # type: ignore[arg-type]
    assert info.value.code == "invalid_config"


def test_statement_token_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sql_migration_lint.lexer.MAX_STATEMENT_TOKENS", 3)
    with pytest.raises(InputTooLargeError):
        split_statements("SELECT a, b, c, d;")
    assert len(split_statements("SELECT a;")) == 1


def test_adjacency_acceptance() -> None:
    assert lint_sql(ADJACENT) == []
    assert lint_sql("UPDATE t SET a = $1 WHERE id = $2;") == []
    findings = lint_sql("ALTER TABLE t ADD COLUMN c int NOT NULL; -- DEFAULT 0")
    assert [f.rule_id for f in findings] == ["SML001"]


def test_comments_never_match() -> None:
    assert lint_sql("-- DROP TABLE t\nSELECT 1;") == []
    assert lint_sql("/* DROP TABLE t; */ SELECT 1;") == []
    assert lint_sql('SELECT "DROP TABLE t";') == []
    assert lint_sql("SELECT $$ DROP TABLE t; $$;") == []


def test_findings_are_sorted_by_position() -> None:
    findings = lint_sql("TRUNCATE a;\n  DROP TABLE b; TRUNCATE c;")
    assert [(f.line, f.column, f.rule_id) for f in findings] == [
        (1, 1, "SML007"),
        (2, 3, "SML002"),
        (2, 17, "SML007"),
    ]
    assert [f.line for f in lint_sql("SELECT 1;\r\nDROP TABLE t;")] == [2]


def test_suppression_acceptance() -> None:
    findings = lint_sql("-- migration-lint: ignore=SML002\nDROP TABLE t;\nDROP TABLE u;")
    assert [f.rule_id for f in findings] == ["SML002"]
    assert findings[0].line == 3


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("-- migration-lint: ignore=SML002,SML007\nDROP TABLE t;", []),
        ("-- migration-lint: ignore=SML002, SML007\nDROP TABLE t;", []),
        ("--migration-lint: ignore=SML002\r\nDROP TABLE t;", []),
        ("-- migration-lint: ignore=SML002\n\nDROP TABLE t;", ["SML002"]),
        ("-- migration-lint: ignore=SML007\nDROP TABLE t;", ["SML002"]),
        ("-- migration-lint: ignore=SML002 extra\nDROP TABLE t;", ["SML002"]),
        ("-- migration-lint: ignore=\nDROP TABLE t;", ["SML002"]),
        ("-- migration-lint: ignore SML002\nDROP TABLE t;", ["SML002"]),
        ("/* migration-lint: ignore=SML002 */\nDROP TABLE t;", ["SML002"]),
    ],
)
def test_suppression_forms(sql: str, expected: list[str]) -> None:
    assert ids(sql) == expected


def test_unknown_rule_in_comment() -> None:
    with pytest.raises(ConfigError) as info:
        lint_sql("-- migration-lint: ignore=SML999\nSELECT 1;")
    assert info.value.code == "unknown_rule"
    with pytest.raises(ConfigError) as lower:
        lint_sql("-- migration-lint: ignore=sml002\nSELECT 1;")
    assert lower.value.code == "unknown_rule"
    with pytest.raises(ConfigError) as long_id:
        lint_sql("-- migration-lint: ignore=" + "A" * 500)
    assert len(str(long_id.value)) <= 200


def test_unknown_rule_in_config() -> None:
    with pytest.raises(ConfigError) as info:
        LintConfig.from_json('{"disabled": ["SML999"]}')
    assert info.value.code == "unknown_rule"


def test_config_disables_and_overrides() -> None:
    config = LintConfig.from_json(
        '{"disabled": ["SML002"], "severity_overrides": {"SML007": "warning"}}'
    )
    assert config.disabled == frozenset({"SML002"})
    assert lint_sql("DROP TABLE t;", config=config) == []
    findings = lint_sql("TRUNCATE t;", config=config)
    assert [f.severity for f in findings] == ["warning"]
    promoted = LintConfig(severity_overrides={"SML003": "error"})
    assert lint_sql("DROP INDEX i;", config=promoted)[0].severity == "error"


def test_config_defaults_and_immutability() -> None:
    config = LintConfig()
    assert config.disabled == frozenset()
    assert dict(config.severity_overrides) == {}
    assert LintConfig.from_json("{}") == config
    assert isinstance(hash(config), int)
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.disabled = frozenset()  # type: ignore[misc]
    with pytest.raises(TypeError):
        config.severity_overrides["SML001"] = "warning"  # type: ignore[index]


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("{", "invalid_config"),
        ("[]", "invalid_config"),
        ("[" * 50_000, "invalid_config"),
        ('{"other": 1}', "invalid_config"),
        ('{"disabled": "SML001"}', "invalid_config"),
        ('{"disabled": [1]}', "invalid_config"),
        ('{"severity_overrides": []}', "invalid_config"),
        ('{"severity_overrides": {"SML001": 1}}', "invalid_config"),
        ('{"severity_overrides": {"SML001": "fatal"}}', "invalid_config"),
        ('{"severity_overrides": {"SML999": "error"}}', "unknown_rule"),
        ("x" * 100_001, "input_too_large"),
    ],
)
def test_config_errors(text: str, code: str) -> None:
    with pytest.raises(MigrationLintError) as info:
        LintConfig.from_json(text)
    assert info.value.code == code
    assert len(str(info.value)) <= 200


def test_direct_config_validation() -> None:
    with pytest.raises(ConfigError) as unknown:
        LintConfig(disabled=frozenset({"SML999"}))
    assert unknown.value.code == "unknown_rule"
    with pytest.raises(ConfigError):
        LintConfig(disabled=frozenset({1}))  # type: ignore[arg-type]
    with pytest.raises(ConfigError):
        LintConfig(severity_overrides={"SML001": ["error"]})  # type: ignore[dict-item]


def test_value_objects_are_frozen() -> None:
    finding = Finding("SML001", "error", 1, 1, "m")
    with pytest.raises(dataclasses.FrozenInstanceError):
        finding.line = 2  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        Statement("x", 1, 1).line = 2  # type: ignore[misc]


def test_error_codes() -> None:
    assert InputTooLargeError("m").code == "input_too_large"
    assert SqlParseError("m", 4).code == "parse_error"
    assert SqlParseError("m", 4).line == 4
    assert ConfigError("m").code == "invalid_config"
    assert ConfigError("m", "unknown_rule").code == "unknown_rule"
