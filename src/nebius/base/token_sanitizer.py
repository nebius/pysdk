"""Token Sanitizer Module.

This module provides functionality for sanitizing sensitive tokens such as access tokens
and credentials by masking their signatures or sensitive parts without masking the
non-sensitive but useful parts. It supports various token formats including Nebius IAM
tokens and JWT tokens.

The module defines token versions with their prefixes, delimiters, and signature
positions, allowing for flexible sanitization based on token type.
"""

from abc import ABC, abstractmethod

MASK_STRING: str = "**"
"""The mask printed instead of sensitive parts of tokens."""

MAX_VISIBLE_PAYLOAD_LENGTH: int = 15
"""Maximum length of visible payload before masking."""

NO_SIGNATURE: int = -1
"""Constant indicating no signature position in the token."""


class TokenVersion:
    """
    Represents a token version with its structural properties.

    This class encapsulates the characteristics of a token format, including
    the prefix, delimiter used to separate parts, the position of the signature
    within the token parts, and the expected number of token parts.

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
Predefined token formats for access tokens.

This dictionary maps version names to TokenVersion objects for supported
access token formats.
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
Predefined token formats for all types of credentials.

This dictionary includes all access token versions plus additional credential
formats like DE1 and JWT.
"""


class TokenSanitizer:
    """
    Main class for sanitizing tokens based on extracted version information.

    This class uses a TokenVersionExtractor to identify the token format and
    applies appropriate sanitization rules to mask sensitive parts like signatures.

    :ivar extractor: The extractor used to determine token version and recognition
        status.

    :param extractor: The extractor to use for token version identification.
    """

    def __init__(self, extractor: "TokenVersionExtractor") -> None:
        self.extractor: TokenVersionExtractor = extractor

    @staticmethod
    def access_token_sanitizer() -> "TokenSanitizer":
        """
        Create a TokenSanitizer configured for access tokens.

        :returns: A sanitizer instance with access token versions.
        """
        return TokenSanitizer(DefaultTokenVersionExtractor(ACCESS_TOKEN_VERSIONS))

    @staticmethod
    def credentials_sanitizer() -> "TokenSanitizer":
        """
        Create a TokenSanitizer configured for credentials.

        :returns: A sanitizer instance with credentials versions.
        """
        return TokenSanitizer(DefaultTokenVersionExtractor(CREDENTIALS_VERSIONS))

    def sanitize(self, token: str) -> str:
        """
        Sanitize a token by masking its sensitive parts.

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
        """
        Check if a token is supported by this sanitizer.

        :param token: The token string to check.
        :returns: True if the token format is supported, False otherwise.
        """
        version, recognized = self.extractor.extract(token)
        if not recognized:
            return False
        token_parts: list[str] = token.split(version.delimiter)
        return len(token_parts) >= version.token_parts_count


def sanitize_no_signature(token: str, prefix: str) -> str:
    """
    Sanitize tokens without signatures by limiting visible payload length.

    For tokens without a signature, this function shows the full token if it's
    short enough, otherwise masks the excess with MASK_STRING.

    :param token: The full token string.
    :param prefix: The prefix of the token version.
    :returns: The sanitized token.
    """
    payload: str = token[len(prefix) :]
    if len(payload) <= MAX_VISIBLE_PAYLOAD_LENGTH:
        return token
    return token[: MAX_VISIBLE_PAYLOAD_LENGTH + len(prefix)] + MASK_STRING


def sanitize_unrecognized(token: str) -> str:
    """
    Sanitize unrecognized tokens by masking after a certain length.

    For tokens that don't match any known format, this function shows a
    portion of the token and masks the rest.

    :param token: The token string to sanitize.
    :returns: The sanitized token.
    """
    if len(token) <= MAX_VISIBLE_PAYLOAD_LENGTH:
        return token + MASK_STRING
    return token[:MAX_VISIBLE_PAYLOAD_LENGTH] + MASK_STRING


class TokenVersionExtractor(ABC):
    """
    Abstract base class for extracting token version from a token string.

    Subclasses must implement the extract method to identify the token format
    and return the corresponding TokenVersion along with recognition status.
    """

    @abstractmethod
    def extract(self, token: str) -> tuple[TokenVersion, bool]:
        """
        Extract the token version from a token string.

        :param token: The token string to analyze.
        :returns: A tuple containing the TokenVersion and a boolean indicating
                  whether the token was recognized.
        """
        ...


class DefaultTokenVersionExtractor(TokenVersionExtractor):
    """
    Default implementation of TokenVersionExtractor using predefined versions.

    This extractor checks if the token starts with any of the predefined prefixes
    and returns the matching TokenVersion.

    :ivar versions: Dictionary of available token versions.

    :param versions: Dictionary of token versions to use for extraction.
    """

    def __init__(self, versions: dict[str, TokenVersion]) -> None:
        self.versions: dict[str, TokenVersion] = versions

    def extract(self, token: str) -> tuple[TokenVersion, bool]:
        """
        Extract the token version by matching prefixes.

        :param token: The token string to analyze.
        :returns: The matching TokenVersion and True if recognized, otherwise
                  a default TokenVersion and False.
        """
        for version in self.versions.values():
            if token.startswith(version.prefix):
                return version, True
        return TokenVersion("", "", NO_SIGNATURE, 0), False
