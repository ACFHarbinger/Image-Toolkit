"""
Compound Tag Query Parser & Evaluator (§2.22 Option C).
======================================================
Parses and evaluates boolean compound tag queries containing:
- Binary operators: ``AND`` (``&&``), ``OR`` (``||``)
- Unary operators: ``NOT`` (``!``), prefix ``-tag``
- Grouping: ``( ... )``
- Quoted strings: ``"blue eyes"``, ``'black hair'``
- Implicit conjunctions: ``solo 1girl -chibi`` -> ``solo AND 1girl AND NOT chibi``
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable, List, Optional, Set, Tuple


def normalize_tag(tag: str) -> str:
    """Normalize tag string for consistent comparison (lowercase, underscores)."""
    return tag.strip().lower().replace(" ", "_")


class TagQueryNode(ABC):
    """Abstract base node for boolean tag expression AST."""

    @abstractmethod
    def evaluate(self, tags: Set[str]) -> bool:
        """Evaluate if the provided set of normalized tags satisfies this expression."""
        raise NotImplementedError

    @abstractmethod
    def referenced_tags(self) -> Set[str]:
        """Return all distinct tag literals referenced in this expression."""
        raise NotImplementedError


class TagLiteralNode(TagQueryNode):
    """Matches presence of a specific tag."""

    def __init__(self, tag: str) -> None:
        self.raw_tag = tag
        self.tag = normalize_tag(tag)

    def evaluate(self, tags: Set[str]) -> bool:
        return self.tag in tags

    def referenced_tags(self) -> Set[str]:
        return {self.tag}

    def __repr__(self) -> str:
        return f"Tag({self.tag!r})"

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, TagLiteralNode) and self.tag == other.tag


class NotNode(TagQueryNode):
    """Boolean negation (NOT / ! / -)."""

    def __init__(self, child: TagQueryNode) -> None:
        self.child = child

    def evaluate(self, tags: Set[str]) -> bool:
        return not self.child.evaluate(tags)

    def referenced_tags(self) -> Set[str]:
        return self.child.referenced_tags()

    def __repr__(self) -> str:
        return f"NOT({self.child!r})"

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, NotNode) and self.child == other.child


class AndNode(TagQueryNode):
    """Boolean conjunction (AND / && / implicit space)."""

    def __init__(self, left: TagQueryNode, right: TagQueryNode) -> None:
        self.left = left
        self.right = right

    def evaluate(self, tags: Set[str]) -> bool:
        return self.left.evaluate(tags) and self.right.evaluate(tags)

    def referenced_tags(self) -> Set[str]:
        return self.left.referenced_tags() | self.right.referenced_tags()

    def __repr__(self) -> str:
        return f"({self.left!r} AND {self.right!r})"

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, AndNode) and self.left == other.left and self.right == other.right


class OrNode(TagQueryNode):
    """Boolean disjunction (OR / ||)."""

    def __init__(self, left: TagQueryNode, right: TagQueryNode) -> None:
        self.left = left
        self.right = right

    def evaluate(self, tags: Set[str]) -> bool:
        return self.left.evaluate(tags) or self.right.evaluate(tags)

    def referenced_tags(self) -> Set[str]:
        return self.left.referenced_tags() | self.right.referenced_tags()

    def __repr__(self) -> str:
        return f"({self.left!r} OR {self.right!r})"

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, OrNode) and self.left == other.left and self.right == other.right


class EmptyQueryNode(TagQueryNode):
    """Matches everything when query is empty."""

    def evaluate(self, tags: Set[str]) -> bool:
        return True

    def referenced_tags(self) -> Set[str]:
        return set()

    def __repr__(self) -> str:
        return "EmptyQuery()"

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, EmptyQueryNode)


class _TokenType:
    TAG = "TAG"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    EOF = "EOF"


class _Token:
    def __init__(self, type_: str, value: str, pos: int) -> None:
        self.type = type_
        self.value = value
        self.pos = pos

    def __repr__(self) -> str:
        return f"Token({self.type}, {self.value!r}, pos={self.pos})"


class CompoundTagQueryParser:
    """Tokenizer and recursive descent parser for compound tag queries."""

    @classmethod
    def tokenize(cls, text: str) -> List[_Token]:
        tokens: List[_Token] = []
        i = 0
        n = len(text)

        while i < n:
            ch = text[i]

            if ch.isspace():
                i += 1
                continue

            if ch == "(":
                tokens.append(_Token(_TokenType.LPAREN, "(", i))
                i += 1
                continue

            if ch == ")":
                tokens.append(_Token(_TokenType.RPAREN, ")", i))
                i += 1
                continue

            # Check quotes
            if ch in ('"', "'"):
                quote_char = ch
                start_pos = i
                i += 1
                content = []
                while i < n and text[i] != quote_char:
                    content.append(text[i])
                    i += 1
                if i < n and text[i] == quote_char:
                    i += 1
                tag_val = "".join(content).strip()
                if tag_val:
                    tokens.append(_Token(_TokenType.TAG, tag_val, start_pos))
                continue

            # Check prefix NOT: '-' or '!' followed immediately by tag/quote/lparen
            if ch in ("-", "!") and i + 1 < n and not text[i + 1].isspace():
                tokens.append(_Token(_TokenType.NOT, "NOT", i))
                i += 1
                continue

            # Check prefix required '+'
            if ch == "+" and i + 1 < n and not text[i + 1].isspace():
                i += 1
                continue

            # Check word / symbol token
            start_pos = i
            while i < n and not text[i].isspace() and text[i] not in ("(", ")", '"', "'"):
                i += 1

            word = text[start_pos:i]
            upper = word.upper()

            if upper in ("AND", "&&", "&"):
                tokens.append(_Token(_TokenType.AND, "AND", start_pos))
            elif upper in ("OR", "||", "|"):
                tokens.append(_Token(_TokenType.OR, "OR", start_pos))
            elif upper in ("NOT", "!"):
                tokens.append(_Token(_TokenType.NOT, "NOT", start_pos))
            else:
                tokens.append(_Token(_TokenType.TAG, word, start_pos))

        tokens.append(_Token(_TokenType.EOF, "", n))
        return tokens

    def __init__(self, query: str) -> None:
        self.raw_query = query
        self.tokens = self.tokenize(query)
        self.pos = 0

    def _peek(self) -> _Token:
        return self.tokens[self.pos]

    def _consume(self, expected_type: Optional[str] = None) -> _Token:
        tok = self.tokens[self.pos]
        if expected_type and tok.type != expected_type:
            raise ValueError(
                f"Expected {expected_type} at position {tok.pos}, found {tok.type} ({tok.value!r})"
            )
        if tok.type != _TokenType.EOF:
            self.pos += 1
        return tok

    def parse(self) -> TagQueryNode:
        """Parse query string into a TagQueryNode AST."""
        if self._peek().type == _TokenType.EOF:
            return EmptyQueryNode()

        node = self._parse_or()
        if self._peek().type != _TokenType.EOF:
            tok = self._peek()
            raise ValueError(f"Unexpected token {tok.value!r} at position {tok.pos}")
        return node

    def _parse_or(self) -> TagQueryNode:
        left = self._parse_and()

        while self._peek().type == _TokenType.OR:
            self._consume(_TokenType.OR)
            right = self._parse_and()
            left = OrNode(left, right)

        return left

    def _parse_and(self) -> TagQueryNode:
        left = self._parse_not()

        while True:
            tok = self._peek()
            if tok.type == _TokenType.AND:
                self._consume(_TokenType.AND)
                right = self._parse_not()
                left = AndNode(left, right)
            # Implicit AND: if next token starts a primary/not expression (TAG, NOT, LPAREN)
            elif tok.type in (_TokenType.TAG, _TokenType.NOT, _TokenType.LPAREN):
                right = self._parse_not()
                left = AndNode(left, right)
            else:
                break

        return left

    def _parse_not(self) -> TagQueryNode:
        if self._peek().type == _TokenType.NOT:
            self._consume(_TokenType.NOT)
            child = self._parse_not()
            return NotNode(child)
        return self._parse_primary()

    def _parse_primary(self) -> TagQueryNode:
        tok = self._peek()

        if tok.type == _TokenType.LPAREN:
            self._consume(_TokenType.LPAREN)
            node = self._parse_or()
            self._consume(_TokenType.RPAREN)
            return node

        if tok.type == _TokenType.TAG:
            self._consume(_TokenType.TAG)
            return TagLiteralNode(tok.value)

        raise ValueError(
            f"Expected tag or '(' at position {tok.pos}, found {tok.type} ({tok.value!r})"
        )


def parse_tag_query(query: str) -> TagQueryNode:
    """Convenience helper to parse a query string into an AST node."""
    if not query or not query.strip():
        return EmptyQueryNode()
    return CompoundTagQueryParser(query).parse()


def validate_tag_query(query: str) -> Tuple[bool, Optional[str]]:
    """Validate query syntax without raising. Returns (is_valid, error_message)."""
    if not query or not query.strip():
        return True, None
    try:
        CompoundTagQueryParser(query).parse()
        return True, None
    except Exception as exc:
        return False, str(exc)


def evaluate_tag_query(query_or_node: str | TagQueryNode, tags: Iterable[str]) -> bool:
    """Evaluate whether an iterable of tag strings satisfies the query."""
    if isinstance(query_or_node, str):
        if not query_or_node.strip():
            return True
        node = parse_tag_query(query_or_node)
    else:
        node = query_or_node

    normalized_tags = {normalize_tag(t) for t in tags if t}
    return node.evaluate(normalized_tags)


def extract_referenced_tags(query_or_node: str | TagQueryNode) -> Set[str]:
    """Return all distinct tag literals referenced in the query."""
    if isinstance(query_or_node, str):
        if not query_or_node.strip():
            return set()
        node = parse_tag_query(query_or_node)
    else:
        node = query_or_node
    return node.referenced_tags()


__all__ = [
    "TagQueryNode",
    "TagLiteralNode",
    "NotNode",
    "AndNode",
    "OrNode",
    "EmptyQueryNode",
    "CompoundTagQueryParser",
    "parse_tag_query",
    "validate_tag_query",
    "evaluate_tag_query",
    "extract_referenced_tags",
    "normalize_tag",
]
