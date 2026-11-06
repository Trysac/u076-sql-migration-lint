"""Tests for the command line interface."""

from __future__ import annotations

import io
import json
import runpy
import sys
from pathlib import Path

import pytest

from sql_migration_lint.__main__ import main

BAD = "ALTER TABLE t ADD COLUMN c int NOT NULL;"
WARN = "CREATE INDEX i ON t (c);"


def write(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


class Recorder(io.StringIO):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.sizes: list[int | None] = []

    def read(self, size: int | None = -1) -> str:
        self.sizes.append(size)
        return super().read(size)


def test_findings_exit_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path, "bad.sql", BAD)
    monkeypatch.chdir(tmp_path)
    assert main(["bad.sql"]) == 1
    assert capsys.readouterr().out.startswith("bad.sql:1:1: SML001 error ")


def test_clean_file_exit_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([write(tmp_path, "ok.sql", "SELECT 1;\n")]) == 0
    assert capsys.readouterr().out == ""


def test_empty_file_exit_zero(tmp_path: Path) -> None:
    assert main([write(tmp_path, "empty.sql", "")]) == 0


def test_missing_path_exit_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(tmp_path / "missing.sql")]) == 2
    assert "missing.sql" in capsys.readouterr().err


def test_parse_error_exit_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([write(tmp_path, "p.sql", "SELECT 'x")]) == 2
    assert "parse_error" in capsys.readouterr().err


def test_directory_and_bad_encoding_exit_two(tmp_path: Path) -> None:
    assert main([str(tmp_path)]) == 2
    binary = tmp_path / "b.sql"
    binary.write_bytes(b"\xff\xfe")
    assert main([str(binary)]) == 2


def test_oversize_file_exit_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([write(tmp_path, "big.sql", "x" * 2_000_001)]) == 2
    assert "input_too_large" in capsys.readouterr().err


def test_json_format(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write(tmp_path, "bad.sql", BAD)
    assert main([path, "--format", "json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert len(data) == 1
    assert list(data[0]) == ["path", "rule_id", "severity", "line", "column", "message"]
    assert data[0]["path"] == path
    assert (data[0]["rule_id"], data[0]["severity"]) == ("SML001", "error")
    assert (data[0]["line"], data[0]["column"]) == (1, 1)


def test_json_format_clean(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([write(tmp_path, "ok.sql", "SELECT 1;"), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_dialect_option(tmp_path: Path) -> None:
    path = write(tmp_path, "i.sql", WARN)
    assert main([path]) == 1
    assert main([path, "--dialect", "postgres"]) == 1
    assert main([path, "--dialect", "generic"]) == 0


def test_fail_on(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    warn = write(tmp_path, "w.sql", WARN)
    bad = write(tmp_path, "e.sql", BAD)
    assert main([warn, "--fail-on", "error"]) == 0
    assert "SML003 warning" in capsys.readouterr().out
    assert main([warn, "--fail-on", "warning"]) == 1
    assert main([bad, "--fail-on", "error"]) == 1


def test_stdin_is_read_with_a_bound(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stream = Recorder("DROP TABLE t;")
    monkeypatch.setattr(sys, "stdin", stream)
    assert main(["-"]) == 1
    assert capsys.readouterr().out.startswith("<stdin>:1:1: SML002 error ")
    assert stream.sizes == [2_000_001]


def test_several_files_with_one_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = write(tmp_path, "bad.sql", BAD)
    assert main([bad, str(tmp_path / "missing.sql")]) == 2
    captured = capsys.readouterr()
    assert "SML001" in captured.out
    assert "missing.sql" in captured.err


def test_config_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = write(tmp_path, "bad.sql", BAD)
    config = write(tmp_path, "c.json", '{"disabled": ["SML001"]}')
    assert main([bad, "--config", config]) == 0
    broken = write(tmp_path, "broken.json", '{"disabled": ["SML999"]}')
    assert main([bad, "--config", broken]) == 2
    assert "unknown_rule" in capsys.readouterr().err
    assert main([bad, "--config", str(tmp_path / "nope.json")]) == 2
    huge = write(tmp_path, "huge.json", " " * 100_001)
    assert main([bad, "--config", huge]) == 2


def test_usage_errors(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2
    assert main(["--dialect", "mysql", "x.sql"]) == 2
    assert main(["--help"]) == 0
    assert "sql-migration-lint" in capsys.readouterr().out


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_module_entry_point(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clean = write(tmp_path, "ok.sql", "SELECT 1;")
    monkeypatch.setattr(sys, "argv", ["sql-migration-lint", clean])
    with pytest.raises(SystemExit) as info:
        runpy.run_module("sql_migration_lint.__main__", run_name="__main__")
    assert info.value.code == 0
