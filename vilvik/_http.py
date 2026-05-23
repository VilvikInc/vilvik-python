"""Shared HTTP plumbing for `vilvik.Client`.

Kept separate from `client.py` so the resource sub-clients (Submissions,
Results, CodeUploads, Webhooks) can each consume a thin transport object
without circular imports.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, Optional

import requests

from vilvik.exceptions import (
    APIError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)

DEFAULT_BASE_URL = "https://vilvik.com/api/v1"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_USER_AGENT = "vilvik-python/0.2.0"

logger = logging.getLogger("vilvik")


class Transport:
    """Wraps `requests.Session` with auth, retry, and error translation."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        session: Optional[requests.Session] = None,
        user_agent: str = DEFAULT_USER_AGENT,
        max_retries: int = 2,
    ):
        if not api_key:
            raise ValueError(
                "api_key is required. Pass it explicitly or set VILVIK_API_KEY.",
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.user_agent = user_agent
        self.max_retries = max(0, int(max_retries))
        self.session = session or requests.Session()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        attempt = 0
        while True:
            try:
                resp = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=json.dumps(json_body) if json_body is not None else None,
                    headers=headers,
                    timeout=timeout or self.timeout,
                )
            except requests.RequestException as exc:
                if attempt < self.max_retries and method.upper() in {"GET", "HEAD"}:
                    attempt += 1
                    sleep_for = 0.5 * (2 ** (attempt - 1))
                    logger.warning(
                        "vilvik: network error on %s %s, retrying in %.1fs (%s)",
                        method,
                        path,
                        sleep_for,
                        exc,
                    )
                    time.sleep(sleep_for)
                    continue
                raise APIError(
                    status_code=0,
                    code="network_error",
                    message=str(exc),
                ) from exc

            # The server may return non-JSON on infrastructure errors (e.g.
            # 502 from a load balancer). Treat those as APIError without
            # trying to decode the body.
            try:
                payload = resp.json() if resp.content else {}
            except ValueError:
                payload = {"raw_body": resp.text[:1000]}

            if 200 <= resp.status_code < 300:
                return payload

            self._raise_for_status(resp, payload)

    @staticmethod
    def _raise_for_status(resp: requests.Response, payload: Dict[str, Any]) -> None:
        status = resp.status_code
        # Vilvik's API errors come back as {"error": {"code": "...", "message": "...", "request_id": "..."}}.
        # Fall back to top-level keys if a proxy returned a different envelope.
        err = payload.get("error") if isinstance(payload, dict) else None
        if not isinstance(err, dict):
            err = payload if isinstance(payload, dict) else {}
        code = str(err.get("code") or "")
        message = str(err.get("message") or err.get("detail") or "")
        request_id = str(err.get("request_id") or resp.headers.get("X-Request-Id") or "")

        if status in (401, 403):
            raise AuthenticationError(status, code, message, request_id, payload)
        if status == 404:
            raise NotFoundError(status, code, message, request_id, payload)
        if status in (400, 422):
            raise ValidationError(status, code, message, request_id, payload)
        if status == 429:
            retry_after_raw = resp.headers.get("Retry-After")
            try:
                retry_after = int(retry_after_raw) if retry_after_raw else None
            except (TypeError, ValueError):
                retry_after = None
            raise RateLimitError(
                status, code, message, request_id, payload, retry_after=retry_after,
            )
        raise APIError(status, code, message, request_id, payload)

    @staticmethod
    def make_idempotency_key() -> str:
        return str(uuid.uuid4())
