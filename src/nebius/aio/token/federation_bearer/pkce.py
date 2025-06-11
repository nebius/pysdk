def generate_pkce_code_verifier() -> str:
    """
    Generate a PKCE code verifier.

    Returns:
        str: A securely generated code verifier.
    """
    import base64
    import secrets

    # Generate a random 32-byte string
    random_bytes = secrets.token_bytes(32)

    # Base64 URL-safe encode the bytes and strip padding
    code_verifier = base64.urlsafe_b64encode(random_bytes).strip(b"=").decode("utf-8")

    return code_verifier


class PKCE(str):
    """
    A class representing a PKCE (Proof Key for Code Exchange) code verifier.
    """

    def __new__(cls) -> "PKCE":
        code_verifier = generate_pkce_code_verifier()
        return str.__new__(cls, code_verifier)

    def __init__(self) -> None:
        super().__init__()

    @property
    def challenge(self) -> str:
        """
        Generate the PKCE code challenge from the code verifier.

        Returns:
            str: The PKCE code challenge.
        """
        import base64
        import hashlib

        # Create a SHA-256 hash of the code verifier
        sha256_hash = hashlib.sha256(self.encode("utf-8")).digest()

        # Base64 URL-safe encode the hash and strip padding
        code_challenge = (
            base64.urlsafe_b64encode(sha256_hash).strip(b"=").decode("utf-8")
        )

        return code_challenge

    @property
    def method(self) -> str:
        """
        Get the PKCE method, which is always 'S256' for SHA-256.

        Returns:
            str: The PKCE method.
        """
        return "S256"

    @property
    def verifier(self) -> str:
        """
        Get the PKCE code verifier.

        Returns:
            str: The PKCE code verifier.
        """
        return str(self)
