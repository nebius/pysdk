"""Parser for Nebius field mask strings.

This module tokenizes and parses the compact mask syntax into a
:class:`nebius.base.fieldmask.Mask` tree. It supports dotted paths, comma
separation, nested sub-masks using parentheses, and the wildcard ``*``.

Grammar overview
----------------

- Paths are dot-separated (``spec.max_size_bytes``).
- Multiple paths are comma-separated.
- Parentheses group a sub-mask (``spec.(a,b)``).
- ``*`` denotes a wildcard branch at the current level.

Examples
--------
Parse a simple mask::

    from nebius.base.fieldmask_parser import parse

    mask = parse("spec.max_size_bytes,labels")
    assert mask.marshal() == "labels,spec.max_size_bytes"

Parse a nested mask::

    mask = parse("spec.(limits,max_size_bytes)")
    assert mask.marshal() == "spec.(limits,max_size_bytes)"

"""

import re
from collections.abc import Generator
from dataclasses import dataclass
from enum import Enum, auto
from json import dumps, loads

from .fieldmask import Error, FieldKey, Mask

simple_string_token_set = "[a-zA-Z0-9_]"  # noqa: S105 # not a password
"""Regex for simple (unquoted) token strings."""
simple_string_token_start = re.compile("^" + simple_string_token_set)
"""Regex for the start of simple (unquoted) token strings."""
simple_string_token = re.compile("^(" + simple_string_token_set + "+)")
"""Regex for full simple (unquoted) token strings."""
space_chars = " \r\n\t"
"""Whitespace characters recognized by the lexer."""
space_set = frozenset(space_chars)
"""Set of whitespace characters recognized by the lexer."""
max_context = 30
"""Maximum length of context to show in error messages."""
context_back = 12
"""Number of characters to show before the error position."""
error_mark = "\u20de"
"""Combining enclosing square to mark error position in context."""


def _possible_ellipsis(s: str, max_context: int) -> str:
    """Return a truncated string with an ellipsis when needed.

    :param s: Source string.
    :param max_context: Maximum length to return.
    :returns: Possibly truncated string.
    """
    if len(s) > max_context:
        return s[: max_context - 3] + "..."
    return s


def _context_around(s: str, pos: int) -> str:
    """Build a human-friendly context string around a parse error.

    :param s: Source string.
    :param pos: Error position within ``s``.
    :returns: Context string with an error mark.
    """
    ctx_start = pos
    if ctx_start >= context_back:
        ctx_start -= context_back
    else:
        ctx_start = 0

    delta = pos - ctx_start
    ctx_str = _possible_ellipsis(s[ctx_start:], max_context)
    with_mark = ctx_str[:delta] + error_mark + ctx_str[delta:]
    return f"at position {pos} near {dumps(with_mark, ensure_ascii=False)}"


_parse_steps_per_char = 8
"""Number of steps that :func:`parse` permits for each character of the input."""


class ParseError(Error):
    """Raised when parsing fails."""


class ContextedParseError(ParseError):
    """Parse error that includes source context.

    :ivar input: Original source string.
    :ivar position: Error position in the source.
    :ivar summary: Short error description.
    """

    def __init__(self, source: str, position: int, summary: str) -> None:
        """Create a parse error with source context.

        :param source: Original source string.
        :param position: Error position in the source.
        :param summary: Short error description.
        """
        self.input = source
        self.position = position
        self.summary = summary

        super().__init__(f"{summary} {_context_around(source, position)}")


class TooComplexError(ContextedParseError):
    """Raised when a mask needs more steps than :func:`parse` permits."""


class TokenType(Enum):
    """Token kinds produced by :class:`Lexer`."""

    COMMA = auto()
    DOT = auto()
    LBRACE = auto()
    RBRACE = auto()
    WILD_CARD = auto()
    PLAIN_KEY = auto()
    QUOTED_KEY = auto()
    EOL = auto()


@dataclass
class Token:
    """Single token with type, string value, and source position.

    :ivar type: Token type.
    :ivar value: Raw token value.
    :ivar pos: Character position in the input.
    """

    type: TokenType
    value: str
    pos: int

    def copy(self) -> "Token":
        """Return a shallow copy of the token."""
        return Token(
            type=self.type,
            value=self.value,
            pos=self.pos,
        )

    def unquote(self) -> "Token":
        """Convert a quoted key token into a plain key token.

        :returns: Token with unquoted value.
        :raises ParseError: If the token cannot be unquoted to a string.
        """
        if self.type != TokenType.QUOTED_KEY:
            return self.copy()
        unquoted = loads(self.value)
        if not isinstance(unquoted, str):
            raise ParseError(f"Token is not a quoted string: {self!r}")
        return Token(
            type=TokenType.PLAIN_KEY,
            value=unquoted,
            pos=self.pos,
        )

    def __repr__(self) -> str:
        """Return a debug representation of the token."""
        if self.type != TokenType.QUOTED_KEY:
            val = dumps(self.value)
        else:
            val = self.value
        return f"Token{self.type.name}({val} pos {self.pos})"


class Lexer:
    """Tokenizer for the field mask grammar.

    :param source: Mask string to tokenize.
    :ivar source: Input string being tokenized.
    :ivar pos: Current cursor position.
    """

    def __init__(self, source: str) -> None:
        self.source = source
        self.pos: int = 0

    def next_token(self) -> Token:
        """Scan and return the next token.

        :returns: Next :class:`Token` instance.
        :raises ContextedParseError: If an unexpected character is found.
        """
        while self.pos < len(self.source) and self.source[self.pos] in space_set:
            self.pos += 1

        if self.pos >= len(self.source):
            return Token(
                type=TokenType.EOL,
                value="",
                pos=self.pos,
            )
        start = self.pos
        if self.starts_with(","):
            self.consume(",")
            return Token(
                type=TokenType.COMMA,
                value=",",
                pos=start,
            )
        elif self.starts_with("."):
            self.consume(".")
            return Token(
                type=TokenType.DOT,
                value=".",
                pos=start,
            )
        elif self.starts_with("("):
            self.consume("(")
            return Token(
                type=TokenType.LBRACE,
                value="(",
                pos=start,
            )
        elif self.starts_with(")"):
            self.consume(")")
            return Token(
                type=TokenType.RBRACE,
                value=")",
                pos=start,
            )
        elif self.starts_with("*"):
            self.consume("*")
            return Token(
                type=TokenType.WILD_CARD,
                value="*",
                pos=start,
            )
        elif self.starts_with('"'):
            return self.scan_quoted_key()
        elif simple_string_token_start.match(self.source[self.pos :]) is not None:
            return self.scan_plain_key()
        else:
            raise ContextedParseError(self.source, self.pos, "unexpected symbol")

    def scan_plain_key(self) -> Token:
        """Scan a plain (unquoted) key token."""
        start = self.pos
        re_match = simple_string_token.match(self.source[start:])
        if re_match is None:
            raise ContextedParseError(self.source, self.pos, "unexpected match mismatch")
        self.consume(re_match[0])
        return Token(
            type=TokenType.PLAIN_KEY,
            value=re_match[0],
            pos=start,
        )

    def scan_quoted_key(self) -> Token:
        """Scan a quoted key token."""
        start = self.pos
        self.consume('"')
        while self.pos < len(self.source) and not self.starts_with('"'):
            if self.starts_with("\\"):
                self.pos += 2
            else:
                self.pos += 1
        if self.starts_with('"'):
            self.consume('"')
            return Token(
                type=TokenType.QUOTED_KEY,
                value=self.source[start : self.pos],
                pos=start,
            )
        raise ContextedParseError(self.source, start, "unterminated quoted string")

    def consume(self, prefix: str) -> None:
        """Advance the lexer position by the length of ``prefix``.

        :param prefix: String to consume.
        """
        self.pos += len(prefix)

    def starts_with(self, prefix: str) -> bool:
        """Return True if the remaining input starts with ``prefix``.

        :param prefix: Prefix to check.
        :returns: ``True`` when the remaining input starts with ``prefix``.
        """
        return self.source[self.pos :].startswith(prefix)

    def __iter__(self) -> Generator[Token, None, None]:
        """Yield tokens until end-of-input."""
        while True:
            tok = self.next_token()
            try:
                tok = tok.unquote()
            except Exception as e:
                raise ContextedParseError(self.source, tok.pos, f"{e}") from e
            if tok.type == TokenType.EOL:
                return
            yield tok


class Level:
    """Parser helper tracking mask branches within a parenthesized level.

    ``starts``, ``ends`` and ``active`` are sets: one mask occurs one time at
    most. Two different masks never share a child. Thus, the size of each set
    is not more than the number of masks in the result.

    :ivar starts: Masks that represent branch starts for the current level.
    :ivar ends: Finished masks retained when a suffix can extend them.
    :ivar active: Masks that are currently being extended.
    :ivar prev: Previous level in the nesting stack.
    :ivar pos: Source position of the opening parenthesis.
    """

    def __init__(self) -> None:
        """Create a new parsing level with a fresh root mask."""
        root = Mask()
        self.starts = list[Mask]([root])
        self.ends = list[Mask]()
        self.active = list[Mask]([root])
        self._ended = set[int]()
        """Identities of the masks in ``ends``."""
        self._collect_ends = False
        """True when a key or a wildcard can extend the masks that this level
        finishes. Only then the level fills ``ends``."""
        self.prev: Level | None = None
        self.pos: int = 0

    def add_key(self, k: FieldKey) -> None:
        """Advance active masks by adding/entering the given key.

        Each active mask gets its own child.

        :param k: Field key to add at the current level.
        """
        new_active = list[Mask]()
        for a in self.active:
            mask = a.field_parts.get(k)
            if mask is None:
                mask = Mask()
                a.field_parts[k] = mask
            new_active.append(mask)
        self.active = new_active

    def add_any(self) -> None:
        """Advance active masks by adding/entering a wildcard branch.

        Each active mask gets its own child.
        """
        new_active = list[Mask]()
        for a in self.active:
            if a.any is None:
                a.any = Mask()
            new_active.append(a.any)
        self.active = new_active

    def _finish(self) -> None:
        """Move the active masks to ``ends``.

        Branches that end at the same mask add it one time.
        """
        if not self._collect_ends:
            return
        for a in self.active:
            if id(a) not in self._ended:
                self._ended.add(id(a))
                self.ends.append(a)

    def new_mask(self) -> None:
        """Start a new top-level mask branch (after a comma)."""
        self._finish()
        self.active = self.starts

    def push_level(self, pos: int, before_dot: bool = False) -> "Level":
        """Enter a nested parenthesized level.

        :param pos: Source position of the opening parenthesis.
        :param before_dot: True when a dot follows the closing parenthesis of
            the new level.
        :returns: New :class:`Level` instance.
        """
        nl = Level()
        nl.pos = pos
        nl.prev = self
        # The parent level gets the finished masks of the new level. Thus, the
        # new level also collects them when the parent level does.
        nl._collect_ends = before_dot or self._collect_ends
        nl.starts = self.active
        nl.active = self.active
        return nl

    def pop_level(self) -> "Level|None":
        """Exit to the previous level, merging active branches.

        The previous level gets no masks when this level does not collect
        them, because no token can use them.
        """
        p = self.prev
        if p is not None:
            self._finish()
            p.active = self.ends
        return p


def _groups_before_dot(tokens: list[Token]) -> list[bool]:
    """Find the groups that a dot follows.

    :param tokens: Tokens of the mask.
    :returns: One value for each token. The value is true for the opening
        parenthesis of such a group.
    """
    ret = [False] * len(tokens)
    opened = list[int]()
    for i, tok in enumerate(tokens):
        if tok.type == TokenType.LBRACE:
            opened.append(i)
        elif tok.type == TokenType.RBRACE:
            if not opened:
                # The parser reports the unmatched parenthesis.
                break
            ret[opened.pop()] = i + 1 < len(tokens) and tokens[i + 1].type == TokenType.DOT
    return ret


class State(Enum):
    """Parser state machine states."""

    KEY = auto()
    SEPARATOR = auto()
    LEVEL_START = auto()


def parse(source: str) -> Mask:
    """Parse a mask string into a :class:`Mask` tree.

    The parser limits its work, because a sequence of groups multiplies the
    number of fields. For example, ``(a,b).(c,d).(e,f)`` contains 14 fields.
    The parser does one step for each active mask when it applies a key, a
    wildcard, a comma or a closing parenthesis. It permits 8 steps for each
    character of the input. The number of fields in the result is thus not
    more than 8 times the length of the input.

    The limit has no effect on a mask in which no dot follows a group. Such a
    mask needs one step for each token at most. :meth:`Mask.marshal` writes
    only such masks.

    :param source: Mask string to parse.
    :returns: Parsed :class:`Mask`. Empty or whitespace-only strings yield an
        empty mask.
    :raises TooComplexError: If the mask needs more steps than the limit.
    :raises ParseError: If the input is malformed.
    """
    if not isinstance(source, str):  # type: ignore[unused-ignore]
        raise ParseError(f"wrong type of source: {type(source)}, expected str")
    return _parse(source, _parse_steps_per_char * len(source))


def _parse(source: str, max_steps: int) -> Mask:
    """Parse a mask string with an explicit limit for the number of steps.

    :param source: Mask string to parse.
    :param max_steps: Maximum number of steps.
    :returns: Parsed :class:`Mask`.
    :raises ParseError: If the input is malformed or needs too many steps.
    """
    if len(source.lstrip(space_chars)) == 0:
        return Mask()
    tokens = [t for t in Lexer(source)]
    before_dot = _groups_before_dot(tokens)
    lvl = Level()
    root = lvl.starts[0]
    pos = 0
    state: State = State.KEY
    steps = 0

    while True:
        if pos >= len(tokens):
            break
        tok = tokens[pos]
        if state != State.LEVEL_START and tok.type not in (TokenType.DOT, TokenType.LBRACE):
            # All other tokens visit each active mask. Count the visits before
            # the level creates or collects masks.
            steps += len(lvl.active)
            if steps > max_steps:
                raise TooComplexError(source, tok.pos, "mask is too complex")
        match state:
            case State.LEVEL_START:
                if tok.type == TokenType.RBRACE:
                    state = State.SEPARATOR
                else:
                    state = State.KEY
                continue
            case State.KEY:
                match tok.type:
                    case TokenType.PLAIN_KEY:
                        lvl.add_key(FieldKey(tok.value))
                        state = State.SEPARATOR
                    case TokenType.WILD_CARD:
                        lvl.add_any()
                        state = State.SEPARATOR
                    case TokenType.LBRACE:
                        lvl = lvl.push_level(tok.pos, before_dot[pos])
                        state = State.LEVEL_START
                    case _:
                        raise ContextedParseError(
                            source,
                            tok.pos,
                            f"unexpected token {tok}, expecting field or submask",
                        )
            case State.SEPARATOR:
                match tok.type:
                    case TokenType.DOT:
                        state = State.KEY
                    case TokenType.COMMA:
                        lvl.new_mask()
                        state = State.KEY
                    case TokenType.RBRACE:
                        lvl_ = lvl.pop_level()
                        if lvl_ is None:
                            raise ContextedParseError(source, tok.pos, "unmatched right brace")
                        lvl = lvl_
                        state = State.SEPARATOR
                    case _:
                        raise ContextedParseError(
                            source,
                            tok.pos,
                            f"unexpected token {tok}, expecting separator or closing brace",
                        )
            case _:  # type: ignore[unused-ignore]
                raise ParseError(f"state machine corruption: unknown state {state}")
        pos += 1
    if lvl.prev is not None:
        raise ContextedParseError(
            source,
            lvl.pos,
            "unclosed left brace",
        )
    if state != State.SEPARATOR:
        raise ParseError("unexpected end of mask")
    # The level helpers do not share masks between branches, thus root is a
    # tree. The copy only fails early for a mask that is too deep.
    return root.copy()
