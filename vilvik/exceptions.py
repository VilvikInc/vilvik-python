"""Typed exception hierarchy for the Vilvik SDK.

All SDK errors derive from `VilvikError` so applications can `except
VilvikError` to catch every SDK failure in one place. Specific subclasses
let callers branch on the kind of failure (auth, validation, rate limit,
etc.) without inspecting status codes.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class VilvikError(Exception):
    """Base class for every SDK-raised error."""


class TimeoutError(VilvikError):
    """A polling helper (e.g. `Results.wait_for`) exceeded its deadline."""


class CaptureError(VilvikError):
    """The SDK could not capture the source for one or more code parameters
    (fitness function or callbacks) and no explicit override was provided.

    The message lists each unresolved role and how to pass it manually.
    """


class APIError(VilvikError):
    """A non-2xx HTTP response from the Vilvik API.

    Attributes
    ----------
    status_code:
        HTTP status returned by the server.
    code:
        Stable machine-readable error code (e.g. "validation_failed").
        Empty string if the server did not return one.
    message:
        Human-readable summary.
    request_id:
        The `X-Request-Id` echoed back by the API (or empty when missing).
        Useful to quote in support requests.
    payload:
        The full decoded JSON body, when available, for debugging.
    """

    def __init__(
        self,
        status_code: int,
        code: str = "",
        message: str = "",
        request_id: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.request_id = request_id
        self.payload = payload or {}
        detail = message or code or f"HTTP {status_code}"
        if request_id:
            detail = f"{detail} (request_id={request_id})"
        super().__init__(detail)


class AuthenticationError(APIError):
    """401 / 403 — invalid, revoked, expired, or under-scoped API key."""


class NotFoundError(APIError):
    """404 — the resource does not exist or is not visible to this key."""


class ValidationError(APIError):
    """400 / 422 — the request body failed server-side validation."""


class RateLimitError(APIError):
    """429 — too many requests for this key's rate limit window.

    `retry_after` is seconds reported by the server's Retry-After header,
    or `None` when the server didn't advise one.
    """

    def __init__(self, *args, retry_after: Optional[int] = None, **kwargs):
        self.retry_after = retry_after
        super().__init__(*args, **kwargs)
