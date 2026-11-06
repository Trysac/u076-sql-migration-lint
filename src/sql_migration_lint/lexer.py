"""Lexer and statement splitter following PostgreSQL documentation section 4.1.

This is not a SQL parser. It separates tokens, comments and statements so that rules can match
unquoted keywords without being fooled by strings, quoted identifiers or comments.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from .errors import ConfigError, InputTooLargeError, SqlParseError, snippet

DEFAULT_MAX_INPUT_CHARS = 2_000_000
MAX_STATEMENT_TOKENS = 200_000
DIRECTIVE_PREFIX = "migration-lint:"

_MAX_COMMENT_CHARS = 1_000
_WS_CHARS = frozenset(chr(code) for code in (9, 10, 11, 12, 13, 32))
_MULTILINE_KINDS = frozenset({"string", "qident", "dollar"})
_BREAK = re.compile(r"\r\n|\r|\n")
_EOL = re.compile(r"[\r\n]")
_BLOCK = re.compile(r"/\*|\*/")
_TAG = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$")
_E_SPECIAL = re.compile(r"[\\']")


@dataclass(frozen=True)
class Statement:
    """One SQL statement.

    Attributes:
        text: source text from the first token up to and including the terminating semicolon.
        line: 1-based line of the first token that is not whitespace or a comment.
        column: 1-based column of that token (CRLF counts as one line break).
    """

    text: str
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class Token:
    """A lexical token. ``value`` is upper-cased for ASCII words and punctuation."""

    kind: str
    value: str
    line: int
    column: int
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class Comment:
    """A line comment that may carry a suppression directive."""

    line: int
    text: str


def check_size(sql: str, limit: int) -> None:
    """Raise InputTooLargeError when ``sql`` is longer than ``limit`` characters."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ConfigError("max_input_chars must be a non-negative integer")
    if len(sql) > limit:
        raise InputTooLargeError(f"input has more than {limit} characters")


def _ident_start(ch: str) -> bool:
    return ch == "_" or "a" <= ch <= "z" or "A" <= ch <= "Z" or ord(ch) >= 128


def _ident_part(ch: str) -> bool:
    return _ident_start(ch) or "0" <= ch <= "9" or ch == "$"


def _unterminated(what: str, sql: str, start: int, line: int) -> SqlParseError:
    quoted = snippet(sql[start : start + 41])
    return SqlParseError(f"unterminated {what} at line {line}: {quoted}", line)


def _quoted_end(sql: str, start: int, quote: str, backslash: bool) -> int:
    """Return the index after the closing quote, or -1 when the literal is unterminated."""
    n = len(sql)
    j = start + 1
    while j < n:
        if backslash:
            m = _E_SPECIAL.search(sql, j)
            if m is None:
                return -1
            k = m.start()
            if sql[k] != quote:
                j = k + 2
                continue
        else:
            k = sql.find(quote, j)
            if k < 0:
                return -1
        if k + 1 < n and sql[k + 1] == quote:
            j = k + 2
            continue
        return k + 1
    return -1


def _block_comment_end(sql: str, start: int, line: int) -> int:
    """Return the index after a nestable block comment, using a depth counter (no recursion)."""
    depth = 1
    j = start + 2
    while depth:
        m = _BLOCK.search(sql, j)
        if m is None:
            raise SqlParseError(f"unterminated block comment at line {line}", line)
        depth += 1 if m.group() == "/*" else -1
        j = m.end()
    return j


def _dollar(sql: str, start: int, line: int) -> tuple[str, str, int]:
    """Classify a ``$`` at a token start: dollar quote, parameter or stray punctuation."""
    m = _TAG.match(sql, start)
    if m is not None:
        tag = m.group()
        k = sql.find(tag, m.end())
        if k < 0:
            raise _unterminated("dollar-quoted string", sql, start, line)
        return "dollar", "", k + len(tag)
    j = start + 1
    while j < len(sql) and "0" <= sql[j] <= "9":
        j += 1
    if j > start + 1:
        return "param", "", j
    return "punct", "$", start + 1


def _advance(sql: str, start: int, end: int, line: int, line_start: int) -> tuple[int, int]:
    for m in _BREAK.finditer(sql, start, end):
        line += 1
        line_start = m.end()
    return line, line_start


def _scan(sql: str) -> Iterator[Token | Comment]:
    n = len(sql)
    i = 0
    line = 1
    line_start = 0
    while i < n:
        ch = sql[i]
        if ch in _WS_CHARS:
            j = i + 1
            while j < n and sql[j] in _WS_CHARS:
                j += 1
            line, line_start = _advance(sql, i, j, line, line_start)
            i = j
            continue
        if sql.startswith("--", i):
            m = _EOL.search(sql, i)
            end = n if m is None else m.start()
            limit = min(end, i + 2 + _MAX_COMMENT_CHARS)
            text = sql[i + 2 : limit]
            if text.lstrip().startswith(DIRECTIVE_PREFIX):
                yield Comment(line, text)
            i = end
            continue
        if sql.startswith("/*", i):
            end = _block_comment_end(sql, i, line)
            line, line_start = _advance(sql, i, end, line, line_start)
            i = end
            continue
        column = i - line_start + 1
        tok_line = line
        kind = "punct"
        value = ch
        end = i + 1
        if ch == "'":
            end = _quoted_end(sql, i, "'", False)
            if end < 0:
                raise _unterminated("string literal", sql, i, tok_line)
            kind, value = "string", ""
        elif ch == '"':
            end = _quoted_end(sql, i, '"', False)
            if end < 0:
                raise _unterminated("quoted identifier", sql, i, tok_line)
            kind, value = "qident", ""
        elif ch == "$":
            kind, value, end = _dollar(sql, i, tok_line)
        elif _ident_start(ch):
            end = i + 1
            while end < n and _ident_part(sql[end]):
                end += 1
            word = sql[i:end]
            if word in ("e", "E") and end < n and sql[end] == "'":
                end = _quoted_end(sql, end, "'", True)
                if end < 0:
                    raise _unterminated("string literal", sql, i, tok_line)
                kind, value = "string", ""
            else:
                kind = "word"
                value = word.upper() if word.isascii() else word
        elif "0" <= ch <= "9":
            end = i + 1
            while end < n and (_ident_part(sql[end]) or sql[end] == "."):
                end += 1
            kind, value = "number", ""
        yield Token(kind, value, tok_line, column, i, end)
        if kind in _MULTILINE_KINDS:
            line, line_start = _advance(sql, i, end, line, line_start)
        i = end


def _statement(sql: str, tokens: list[Token], end: int) -> Statement:
    first = tokens[0]
    return Statement(sql[first.start : end], first.line, first.column)


def iter_statements(
    sql: str,
    on_comment: Callable[[int, str], None] | None = None,
) -> Iterator[tuple[Statement, list[Token]]]:
    """Yield each statement with its tokens (the terminating semicolon excluded).

    Directive-looking line comments are reported through ``on_comment(line, text)`` as they are
    scanned, always before the statement that follows them is yielded.
    """
    tokens: list[Token] = []
    for item in _scan(sql):
        if isinstance(item, Comment):
            if on_comment is not None:
                on_comment(item.line, item.text)
            continue
        if item.kind == "punct" and item.value == ";":
            if tokens:
                yield _statement(sql, tokens, item.end), tokens
                tokens = []
            continue
        tokens.append(item)
        if len(tokens) > MAX_STATEMENT_TOKENS:
            raise InputTooLargeError(f"statement has more than {MAX_STATEMENT_TOKENS} tokens")
    if tokens:
        yield _statement(sql, tokens, tokens[-1].end), tokens


def split_statements(
    sql: str,
    *,
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS,
) -> list[Statement]:
    """Split ``sql`` into statements, honoring PostgreSQL quoting and comment rules.

    Semicolons inside strings, quoted identifiers, dollar quotes and comments do not split.
    Empty statements and comment-only text yield nothing; a missing final semicolon is fine.

    Raises:
        InputTooLargeError: if ``sql`` is longer than ``max_input_chars`` (checked first).
        SqlParseError: on an unterminated string, identifier, dollar quote or block comment.
    """
    check_size(sql, max_input_chars)
    return [statement for statement, _ in iter_statements(sql)]
