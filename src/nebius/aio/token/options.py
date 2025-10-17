"""Request option keys used by the token renewal machinery.

This module defines string constants that are used as keys in the
``options`` mapping passed to per-request :class:`Receiver.fetch` calls
and similar APIs. The values associated with these keys are interpreted
by the renewal and exchangeable bearers to control retry and renewal
behaviour.

General conventions
-------------------
- Boolean flags: options that act as switches (for example
  :data:`OPTION_RENEW_SYNCHRONOUS`) are enabled when the key is present
  in the options mapping and its value is not an empty string. The exact
  string value is ignored; presence/non-empty is considered ``True``.
- Numeric overrides: some options accept numeric values encoded as
  strings (for example :data:`OPTION_MAX_RETRIES` and
  :data:`OPTION_RENEW_REQUEST_TIMEOUT`). These are parsed using
  :func:`int` or :func:`float` respectively; invalid values are logged
  and ignored, falling back to implementation defaults.

Options
-------

:data:`OPTION_MAX_RETRIES`
        Key: ``"max_fetch_token_retries"``

        When present in the request ``options`` mapping this key overrides
        the configured maximum number of fetch retries for the current
        receiver. The value must be a decimal integer encoded as a string
        (for example ``"3"``). If the value cannot be parsed as an
        integer it is ignored and the receiver's configured default is
        used (typically ``2``).

:data:`OPTION_RENEW_REQUIRED`
        Key: ``"token_renew_required"``

        A boolean-like flag that forces the bearer to perform a renewal
        even if the cached token would normally be considered fresh. Any
        non-empty string value will enable the behaviour; typically the key
        is set to ``"1"`` or ``"true"`` in examples.

:data:`OPTION_RENEW_SYNCHRONOUS`
        Key: ``"token_renew_synchronous"``

        When present and non-empty this flag requests a synchronous renewal
        for the current fetch operation. In synchronous mode the caller
        waits for a fresh token to be retrieved before :meth:`Receiver.fetch`
        returns (subject to the usual timeout). Note that synchronous
        requests may also suppress triggering a background renewal from the
        receiver's retry logic.

:data:`OPTION_REPORT_ERROR`
        Key: ``"token_renew_report_error"``

        When set, renewal errors are reported back to the caller of
        :meth:`Receiver.fetch` by raising an exception instead of being
        handled silently by background retry logic. This is useful when the
        client needs immediate visibility of renewal failures.

:data:`OPTION_RENEW_REQUEST_TIMEOUT`
        Key: ``"token_renew_request_timeout"``

        Numeric override controlling the timeout (in seconds) used for a
        synchronous renewal request. The value must be a floating-point
        number encoded as a string (for example ``"2.5"``). If the value
        cannot be parsed as a float the option is ignored and the bearer's
        configured default timeout is used (typically 5 seconds).

Examples
--------

Typical usage when requesting a synchronous renewal with a short
timeout::

        options = {
                OPTION_RENEW_REQUIRED: "1",
                OPTION_RENEW_SYNCHRONOUS: "1",
                OPTION_RENEW_REQUEST_TIMEOUT: "0.2",
        }

Override the maximum number of retries for a specific fetch::

        options = {
                OPTION_MAX_RETRIES: "5",
        }

Notes
-----
Implementations that read these options generally follow the patterns
used in :mod:`nebius.aio.token.renewable` and
:mod:`nebius.aio.token.exchangeable`: boolean flags are tested by
checking for a non-empty value, while numeric overrides are parsed and
validated. Invalid numeric values are logged and ignored.
"""

OPTION_MAX_RETRIES = "max_fetch_token_retries"
"""Override the maximum number of token fetch retries for a
single receiver.

When provided in a request ``options`` mapping the value must be a
decimal integer encoded as a string (for example ``"3"``). If the
value cannot be parsed as an integer the option is ignored and the
receiver's configured default is used.
"""
OPTION_RENEW_REQUIRED = "token_renew_required"
"""Boolean-like flag that forces a token renewal.

Any non-empty string value (commonly ``"1"`` or ``"true"``)
enables the behaviour; presence of the key signals that the cached
token should be refreshed even if it would normally be considered
fresh.
"""
OPTION_RENEW_SYNCHRONOUS = "token_renew_synchronous"
"""Request a synchronous renewal for the current fetch.

When this key is present with a non-empty value the fetch operation
will block until a new token has been retrieved (subject to the
fetch timeout and the optional :data:`OPTION_RENEW_REQUEST_TIMEOUT`
override).
"""
OPTION_REPORT_ERROR = "token_renew_report_error"
"""When set, report renewal errors to the caller.

If present and non-empty renewal errors are propagated to the caller
of :meth:`Receiver.fetch` (instead of being handled by background
retry logic). This is useful for callers that need immediate
visibility of failures.
"""
OPTION_RENEW_REQUEST_TIMEOUT = "token_renew_request_timeout"
"""Floating-point timeout (in seconds) used for synchronous
renewal requests.

The value is parsed using :func:`float` (for example ``"2.5"``).
Invalid values are ignored and the bearer's configured default is
used.
"""
