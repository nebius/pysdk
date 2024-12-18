from abc import ABC, abstractmethod

MASK_STRING: str = "**"
MAX_VISIBLE_PAYLOAD_LENGTH: int = 15
NO_SIGNATURE: int = -1


class TokenVersion:
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

CREDENTIALS_VERSIONS: dict[str, TokenVersion] = {
    **ACCESS_TOKEN_VERSIONS,
    "DE1": TokenVersion(
        prefix="nd1", delimiter=".", signature_position=1, token_parts_count=2
    ),
    "JWT": TokenVersion(
        prefix="eyJ", delimiter=".", signature_position=2, token_parts_count=3
    ),
}


class TokenSanitizer:
    def __init__(self, extractor: "TokenVersionExtractor") -> None:
        self.extractor: TokenVersionExtractor = extractor

    @staticmethod
    def access_token_sanitizer() -> "TokenSanitizer":
        return TokenSanitizer(DefaultTokenVersionExtractor(ACCESS_TOKEN_VERSIONS))

    @staticmethod
    def credentials_sanitizer() -> "TokenSanitizer":
        return TokenSanitizer(DefaultTokenVersionExtractor(CREDENTIALS_VERSIONS))

    def sanitize(self, token: str) -> str:
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
        version, recognized = self.extractor.extract(token)
        if not recognized:
            return False
        token_parts: list[str] = token.split(version.delimiter)
        return len(token_parts) >= version.token_parts_count


def sanitize_no_signature(token: str, prefix: str) -> str:
    payload: str = token[len(prefix) :]
    if len(payload) <= MAX_VISIBLE_PAYLOAD_LENGTH:
        return token
    return token[: MAX_VISIBLE_PAYLOAD_LENGTH + len(prefix)] + MASK_STRING


def sanitize_unrecognized(token: str) -> str:
    if len(token) <= MAX_VISIBLE_PAYLOAD_LENGTH:
        return token + MASK_STRING
    return token[:MAX_VISIBLE_PAYLOAD_LENGTH] + MASK_STRING


class TokenVersionExtractor(ABC):
    @abstractmethod
    def extract(self, token: str) -> tuple[TokenVersion, bool]: ...


class DefaultTokenVersionExtractor(TokenVersionExtractor):
    def __init__(self, versions: dict[str, TokenVersion]) -> None:
        self.versions: dict[str, TokenVersion] = versions

    def extract(self, token: str) -> tuple[TokenVersion, bool]:
        for version in self.versions.values():
            if token.startswith(version.prefix):
                return version, True
        return TokenVersion("", "", NO_SIGNATURE, 0), False
