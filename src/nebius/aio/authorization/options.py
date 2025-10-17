"""Authorization options for requests."""

OPTION_TYPE = "type"
"""The type of the authorization in process.

Possible values are defined in :class:`Types`.

Currently, the only supported types are "default" and "disable".
The default type authorizes requests using the configured
authorization provider, if any. The disable type disables
authorization for the request completely (for instance, to perform requests for the
authorization itself).
"""


class Types:
    """The types of the authorization in process."""

    DEFAULT = "default"
    """The default type of authorization. Not used anywhere, appears here for clarity.
    """
    DISABLE = "disable"
    """Disable authorization for the request completely.

    Used to perform requests for the authorization itself, or to send requests without
    any authorization.
    """
