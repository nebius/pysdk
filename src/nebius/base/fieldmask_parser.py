import re
from collections.abc import Generator
from dataclasses import dataclass
from enum import Enum, auto
from json import dumps, loads

from .fieldmask import Error, FieldKey, Mask

simple_string_token_set = "[a-zA-Z0-9_]"  # noqa: S105 # not a password
simple_string_token_start = re.compile("^" + simple_string_token_set)
simple_string_token = re.compile("^(" + simple_string_token_set + "+)")
space_chars = " \r\n\t"
space_set = frozenset(space_chars)
max_context = 30  # maximum length of context to show in error messages.
context_back = 12  # number of characters to show before the error position.
error_mark = "\u20de"  # combining enclosing square


def _possible_ellipsis(s: str, max_context: int) -> str:
    if len(s) > max_context:
        return s[: max_context - 3] + "..."
    return s


def _context_around(s: str, pos: int) -> str:
    ctx_start = pos
    if ctx_start >= context_back:
        ctx_start -= context_back
    else:
        ctx_start = 0

    delta = pos - ctx_start
    ctx_str = _possible_ellipsis(s[ctx_start:], max_context)
    with_mark = ctx_str[:delta] + error_mark + ctx_str[delta:]
    return f"at position {pos} near {dumps(with_mark, ensure_ascii=False)}"


class ParseError(Error):
    pass


class ContextedParseError(ParseError):
    def __init__(self, source: str, position: int, summary: str) -> None:
        self.input = source
        self.position = position
        self.summary = summary

        super().__init__(f"{summary} {_context_around(source, position)}")


class TokenType(Enum):
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
    type: TokenType
    value: str
    pos: int

    def copy(self) -> "Token":
        return Token(
            type=self.type,
            value=self.value,
            pos=self.pos,
        )

    def unquote(self) -> "Token":
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
        if self.type != TokenType.QUOTED_KEY:
            val = dumps(self.value)
        else:
            val = self.value
        return f"Token{self.type.name}({val} pos {self.pos})"


class Lexer:
    def __init__(self, source: str) -> None:
        self.source = source
        self.pos: int = 0

    def next_token(self) -> Token:
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
        start = self.pos
        re_match = simple_string_token.match(self.source[start:])
        if re_match is None:
            raise ContextedParseError(
                self.source, self.pos, "unexpected match mismatch"
            )
        self.consume(re_match[0])
        return Token(
            type=TokenType.PLAIN_KEY,
            value=re_match[0],
            pos=start,
        )

    def scan_quoted_key(self) -> Token:
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
        self.pos += len(prefix)

    def starts_with(self, prefix: str) -> bool:
        return self.source[self.pos :].startswith(prefix)

    def __iter__(self) -> Generator[Token, None, None]:
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
    def __init__(self) -> None:
        root = Mask()
        self.starts = list[Mask]([root])
        self.ends = list[Mask]()
        self.active = list[Mask]([root])
        self.prev: Level | None = None
        self.pos: int = 0

    def add_key(self, k: FieldKey) -> None:
        mask: Mask | None = None
        new_active = list[Mask]()
        for a in self.active:
            if k in a.field_parts:
                new_active.append(a.field_parts[k])
            else:
                if mask is None:
                    mask = Mask()
                    new_active.append(mask)
                a.field_parts[k] = mask
        self.active = new_active

    def add_any(self) -> None:
        mask: Mask | None = None
        new_active = list[Mask]()
        for a in self.active:
            if a.any is not None:
                new_active.append(a.any)
            else:
                if mask is None:
                    mask = Mask()
                    new_active.append(mask)
                a.any = mask
        self.active = new_active

    def new_mask(self) -> None:
        self.ends.extend(self.active)
        self.active = self.starts

    def push_level(self, pos: int) -> "Level":
        nl = Level()
        nl.pos = pos
        nl.prev = self
        nl.starts = self.active
        nl.active = self.active
        return nl

    def pop_level(self) -> "Level|None":
        p = self.prev
        if p is not None:
            p.active = self.ends
            p.active.extend(self.active)
        return p


class State(Enum):
    KEY = auto()
    SEPARATOR = auto()
    LEVEL_START = auto()


def parse(source: str) -> Mask:
    if not isinstance(source, str):  # type: ignore[unused-ignore]
        raise ParseError(f"wrong type of source: {type(source)}, expected str")
    if len(source.lstrip(space_chars)) == 0:
        return Mask()
    tokens = [t for t in Lexer(source)]
    lvl = Level()
    root = lvl.starts[0]
    pos = 0
    state: State = State.KEY

    while True:
        if pos >= len(tokens):
            break
        tok = tokens[pos]
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
                        lvl = lvl.push_level(tok.pos)
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
                            raise ContextedParseError(
                                source, tok.pos, "unmatched right brace"
                            )
                        lvl = lvl_
                        state = State.SEPARATOR
                    case _:
                        raise ContextedParseError(
                            source,
                            tok.pos,
                            f"unexpected token {tok}, expecting separator or closing"
                            " brace",
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
    return root.copy()
