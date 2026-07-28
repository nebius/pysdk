"""Remove sensitive parts from tokens.

This module masks signatures and other sensitive token parts. It keeps useful
nonsensitive parts visible. It supports Nebius IAM tokens and JWT tokens.
Token-version definitions specify prefixes, delimiters, and signature
positions.
"""

from abc import ABC, abstractmethod

MASK_STRING: str = "**"
"""The mask printed instead of sensitive parts of tokens."""

MAX_VISIBLE_PAYLOAD_LENGTH: int = 15
"""Maximum length of visible payload before masking."""

NO_SIGNATURE: int = -1
"""Constant indicating no signature position in the token."""


class TokenVersion:
    """Describe the structure of a token version.

    The structure contains a prefix, a delimiter, a signature position, and an
    expected number of token parts.

    :ivar prefix: The prefix that identifies this token version.
    :ivar delimiter: The delimiter used to split the token into parts.
    :ivar signature_position: The zero-based index of the signature part in the token.
    :ivar token_parts_count: The expected number of parts when the token is split by
        delimiter.

    :param prefix: The prefix that identifies this token version.
    :param delimiter: The delimiter used to split the token into parts.
    :param signature_position: The zero-based index of the signature part.
    :param token_parts_count: The expected number of parts.
    """

    def __init__(
        self,
        prefix: str,
        delimiter: str,
        signature_position: int,
        token_parts_count: int,
    ):
        self.prefix: str = prefix
        self.delimiter: str = delimiter
        self.signature_position: int = signature_position
        self.token_parts_count: int = token_parts_count


ACCESS_TOKEN_VERSIONS: dict[str, TokenVersion] = {
    "V0": TokenVersion(
        prefix="v0.",
        delimiter=".",
        signature_position=NO_SIGNATURE,
        token_parts_count=1,
    ),
    "NE1": TokenVersion(
        prefix="ne1", delimiter=".", signature_position=1, token_parts_count=2
    ),
}
"""
Supported access-token formats.

The keys are version names. The values describe each format.
"""

CREDENTIALS_VERSIONS: dict[str, TokenVersion] = {
    **ACCESS_TOKEN_VERSIONS,
    "DE1": TokenVersion(
        prefix="nd1", delimiter=".", signature_position=1, token_parts_count=2
    ),
    "JWT": TokenVersion(
        prefix="eyJ", delimiter=".", signature_position=2, token_parts_count=3
    ),
}
"""
Supported credential formats.

The mapping contains all access-token formats, DE1, and JWT.
"""


class TokenSanitizer:
    """Mask sensitive token parts according to the token version.

    A :class:`TokenVersionExtractor` identifies the token format. The
    sanitizer then masks sensitive parts such as signatures.

    :ivar extractor: The extractor used to determine token version and recognition
        status.

    :param extractor: The extractor to use for token version identification.
    """

    def __init__(self, extractor: "TokenVersionExtractor") -> None:
        self.extractor: TokenVersionExtractor = extractor

    @staticmethod
    def access_token_sanitizer() -> "TokenSanitizer":
        """Create a sanitizer for access tokens.

        :returns: A sanitizer instance with access token versions.
        """
        return TokenSanitizer(DefaultTokenVersionExtractor(ACCESS_TOKEN_VERSIONS))

    @staticmethod
    def credentials_sanitizer() -> "TokenSanitizer":
        """Create a sanitizer for credentials.

        :returns: A sanitizer instance with credentials versions.
        """
        return TokenSanitizer(DefaultTokenVersionExtractor(CREDENTIALS_VERSIONS))

    def sanitize(self, token: str) -> str:
        """Mask the sensitive parts of a token.

        :param token: The token string to sanitize.
        :returns: The sanitized token with sensitive parts masked.
        """
        if not token:
            return ""

        version, recognized = self.extractor.extract(token)
        if not recognized:
            return sanitize_unrecognized(token)

        token_parts: list[str] = token.split(version.delimiter)

        if version.signature_position == NO_SIGNATURE:
            return sanitize_no_signature(token, version.prefix)

        if len(token_parts) <= version.signature_position:
            return sanitize_unrecognized(token)

        token_parts[version.signature_position] = MASK_STRING
        return version.delimiter.join(token_parts)

    def is_supported(self, token: str) -> bool:
        """Return whether this sanitizer supports the token format.

        :param token: The token string to check.
        :returns: True if the token format is supported, False otherwise.
        """
        version, recognized = self.extractor.extract(token)
        if not recognized:
            return False
        token_parts: list[str] = token.split(version.delimiter)
        return len(token_parts) >= version.token_parts_count


def sanitize_no_signature(token: str, prefix: str) -> str:
    """Limit the visible payload of a token that has no signature.

    Return the complete token if its payload is not too long. Otherwise,
    replace the end of the payload with :data:`MASK_STRING`.

    :param token: The full token string.
    :param prefix: The prefix of the token version.
    :returns: The sanitized token.
    """
    payload: str = token[len(prefix) :]
    if len(payload) <= MAX_VISIBLE_PAYLOAD_LENGTH:
        return token
    return token[: MAX_VISIBLE_PAYLOAD_LENGTH + len(prefix)] + MASK_STRING


def sanitize_unrecognized(token: str) -> str:
    """Limit the visible part of an unrecognized token.

    Show the first part of the token and mask the remaining part.

    :param token: The token string to sanitize.
    :returns: The sanitized token.
    """
    if len(token) <= MAX_VISIBLE_PAYLOAD_LENGTH:
        return token + MASK_STRING
    return token[:MAX_VISIBLE_PAYLOAD_LENGTH] + MASK_STRING


class TokenVersionExtractor(ABC):
    """Define the interface that identifies a token version.

    Subclasses must implement :meth:`extract`.
    """

    @abstractmethod
    def extract(self, token: str) -> tuple[TokenVersion, bool]:
        """Get the token version from a token string.

        :param token: The token string to analyze.
        :returns: A tuple containing the TokenVersion and a boolean indicating
                  whether the token was recognized.
        """
        ...


class DefaultTokenVersionExtractor(TokenVersionExtractor):
    """Identify token versions from a predefined mapping.

    The extractor returns the version with a prefix that matches the token.

    :ivar versions: Dictionary of available token versions.

    :param versions: Dictionary of token versions to use for extraction.
    """

    def __init__(self, versions: dict[str, TokenVersion]) -> None:
        self.versions: dict[str, TokenVersion] = versions

    def extract(self, token: str) -> tuple[TokenVersion, bool]:
        """Get the token version that has a matching prefix.

        :param token: The token string to analyze.
        :returns: The matching TokenVersion and True if recognized, otherwise
                  a default TokenVersion and False.
        """
        for version in self.versions.values():
            if token.startswith(version.prefix):
                return version, True
        return TokenVersion("", "", NO_SIGNATURE, 0), False
