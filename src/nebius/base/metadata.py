class Internal:
    """
    Metadata tags for internal usage, that will be filtered out.

    All the tags must be prefixed with `PREFIX`, by which they will be filtered.
    The PREFIX is constructed such that if it leaks into the actual GRPC, it will cause
    an error.
    """

    PREFIX = ":NebiusInternal:"

    AUTHORIZATION = PREFIX + "authorization"


class Authorization:
    DISABLE = "disable"
