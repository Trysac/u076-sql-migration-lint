"""Rule catalogue and per-statement rule analysis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import pairwise
from types import MappingProxyType

from .errors import ConfigError, snippet
from .lexer import Token

RULE_SEVERITIES: Mapping[str, str] = MappingProxyType(
    {
        "SML001": "error",
        "SML002": "error",
        "SML003": "warning",
        "SML004": "warning",
        "SML005": "warning",
        "SML006": "warning",
        "SML007": "error",
        "SML008": "error",
        "SML009": "error",
        "SML010": "warning",
    }
)

RULE_MESSAGES: Mapping[str, str] = MappingProxyType(
    {
        "SML001": "ADD COLUMN NOT NULL without DEFAULT fails on populated tables",
        "SML002": "DROP TABLE or DROP COLUMN permanently loses data",
        "SML003": "CREATE or DROP INDEX without CONCURRENTLY blocks writes on the table",
        "SML004": "ALTER COLUMN TYPE rewrites the table under an ACCESS EXCLUSIVE lock",
        "SML005": "RENAME breaks running code and takes an ACCESS EXCLUSIVE lock",
        "SML006": "ADD CONSTRAINT without NOT VALID scans the whole table under lock",
        "SML007": "TRUNCATE removes all rows and takes an ACCESS EXCLUSIVE lock",
        "SML008": "CONCURRENTLY cannot run inside a transaction block",
        "SML009": "UPDATE or DELETE without WHERE affects every row",
        "SML010": "SET NOT NULL scans the whole table under an ACCESS EXCLUSIVE lock",
    }
)

GENERIC_DISABLED: frozenset[str] = frozenset({"SML003", "SML006", "SML008", "SML010"})
MAX_FINDINGS_PER_STATEMENT = 10

_CONSTRAINT_STARTS = frozenset({"CONSTRAINT", "CHECK", "FOREIGN", "PRIMARY", "UNIQUE", "EXCLUDE"})
_CONCURRENT_STARTS = frozenset({"CREATE", "DROP", "REINDEX", "REFRESH", "ALTER"})
_RENAME_FOLLOWERS = frozenset({"TO", "VALUE", "ATTRIBUTE", "COLUMN"})


def require_known_rule(rule_id: str) -> None:
    """Raise ConfigError (code ``unknown_rule``) unless ``rule_id`` is a known rule."""
    if rule_id not in RULE_SEVERITIES:
        raise ConfigError(f"unknown rule id: {snippet(rule_id)}", "unknown_rule")


def _at(items: Sequence[str], index: int) -> str:
    return items[index] if 0 <= index < len(items) else ""


def _is_name(token: Token) -> bool:
    return token.kind in ("word", "qident")


def _is_punct(tokens: Sequence[Token], index: int, value: str) -> bool:
    if not 0 <= index < len(tokens):
        return False
    return tokens[index].kind == "punct" and tokens[index].value == value


def _has_pair(words: Sequence[str], first: str, second: str) -> bool:
    return any(a == first and b == second for a, b in pairwise(words))


def _view(tokens: Sequence[Token]) -> tuple[list[int], list[str]]:
    """Return the parenthesis depth per token and the depth-0 keyword view ("" elsewhere)."""
    depth = 0
    depths: list[int] = []
    top: list[str] = []
    for token in tokens:
        if token.kind == "punct" and token.value == ")":
            depth = max(depth - 1, 0)
        depths.append(depth)
        top.append(token.value if token.kind == "word" and depth == 0 else "")
        if token.kind == "punct" and token.value == "(":
            depth += 1
    return depths, top


def _skip_name(tokens: Sequence[Token], index: int) -> int:
    if 0 <= index < len(tokens) and _is_name(tokens[index]):
        index += 1
        while (
            index + 1 < len(tokens)
            and _is_punct(tokens, index, ".")
            and _is_name(tokens[index + 1])
        ):
            index += 2
    return index


def _add_action(seg: Sequence[str]) -> list[str]:
    nxt = _at(seg, 1)
    if nxt in _CONSTRAINT_STARTS:
        j = 3 if nxt == "CONSTRAINT" else 1
        kind = _at(seg, j)
        is_target = kind == "CHECK" or (kind == "FOREIGN" and _at(seg, j + 1) == "KEY")
        if is_target and not _has_pair(seg, "NOT", "VALID"):
            return ["SML006"]
        return []
    start = 2 if nxt == "COLUMN" else 1
    body = seg[start:]
    if _has_pair(body, "NOT", "NULL") and "DEFAULT" not in body:
        return ["SML001"]
    return []


def _alter_action(tokens: Sequence[Token], seg: Sequence[str]) -> list[str]:
    k = 2 if _at(seg, 1) == "COLUMN" else 1
    if k >= len(tokens) or not _is_name(tokens[k]):
        return []
    k += 1
    tail = list(seg[k : k + 3])
    if _at(seg, k) == "TYPE" or tail == ["SET", "DATA", "TYPE"]:
        return ["SML004"]
    if tail == ["SET", "NOT", "NULL"]:
        return ["SML010"]
    return []


def _action(tokens: Sequence[Token], seg: Sequence[str]) -> list[str]:
    head = seg[0]
    if head == "ADD":
        return _add_action(seg)
    if head == "DROP":
        return ["SML002"] if len(seg) > 1 and seg[1] != "CONSTRAINT" else []
    if head == "RENAME":
        return ["SML005"]
    if head == "ALTER":
        return _alter_action(tokens, seg)
    return []


def _alter_table(tokens: Sequence[Token], depths: Sequence[int], top: Sequence[str]) -> list[str]:
    i = 2
    if _at(top, i) == "IF" and _at(top, i + 1) == "EXISTS":
        i += 2
    if _at(top, i) == "ONLY":
        i += 1
    i = _skip_name(tokens, i)
    if _is_punct(tokens, i, "*"):
        i += 1
    hits: list[str] = []
    lo = i
    for j in range(i, len(tokens) + 1):
        if j == len(tokens) or (_is_punct(tokens, j, ",") and depths[j] == 0):
            if j > lo:
                hits.extend(_action(tokens[lo:j], top[lo:j]))
            lo = j + 1
    return hits


def _renames(top: Sequence[str]) -> bool:
    return any(
        word == "RENAME" and _at(top, index + 1) in _RENAME_FOLLOWERS
        for index, word in enumerate(top)
    )


def _statement_hits(
    tokens: Sequence[Token], depths: Sequence[int], top: Sequence[str]
) -> list[str]:
    first = _at(top, 0)
    second = _at(top, 1)
    if first == "ALTER":
        if second == "TABLE":
            return _alter_table(tokens, depths, top)
        return ["SML005"] if _renames(top) else []
    if first == "DROP":
        if second == "TABLE":
            return ["SML002"]
        if second == "INDEX" and _at(top, 2) != "CONCURRENTLY":
            return ["SML003"]
        return []
    if first == "CREATE":
        index_at = 2 if second == "UNIQUE" else 1
        if _at(top, index_at) == "INDEX" and _at(top, index_at + 1) != "CONCURRENTLY":
            return ["SML003"]
        return []
    if first == "TRUNCATE":
        return ["SML007"]
    if first in ("UPDATE", "DELETE") and "WHERE" not in top:
        return ["SML009"]
    return []


def _next_tx(top: Sequence[str], in_tx: bool) -> bool:
    first = _at(top, 0)
    second = _at(top, 1)
    if first == "BEGIN" or (first == "START" and second == "TRANSACTION"):
        return True
    if first in ("COMMIT", "ROLLBACK"):
        if second == "PREPARED" or (first == "ROLLBACK" and "TO" in top):
            return in_tx
        return False
    return in_tx


def analyze_statement(tokens: Sequence[Token], in_tx: bool) -> tuple[list[str], bool]:
    """Return the rule ids hit by one statement and the in-transaction flag after it."""
    depths, top = _view(tokens)
    hits = _statement_hits(tokens, depths, top)
    if in_tx and _at(top, 0) in _CONCURRENT_STARTS and "CONCURRENTLY" in top:
        hits.append("SML008")
    return list(dict.fromkeys(hits)), _next_tx(top, in_tx)
