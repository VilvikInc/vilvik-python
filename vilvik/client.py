"""High-level entrypoint: `vilvik.Client`.

Modelled after `stripe.StripeClient` — one top-level object that
namespaces resources (`client.submissions`, `client.results`, …). Each
resource class is a thin wrapper over `Transport` that converts JSON
into the dataclasses in `vilvik.models`.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Iterable, Iterator, List, Optional

from vilvik._capture import CODE_ROLES, _detect_entry_from_source
from vilvik._http import DEFAULT_BASE_URL, DEFAULT_TIMEOUT_SECONDS, Transport
from vilvik.exceptions import TimeoutError as VilvikTimeout
from vilvik.models import CodeUpload, ImportRecord, Page, Result, Submission, Webhook


def _cursor_from_next(next_url: Optional[str]) -> Optional[str]:
    """Pull the `cursor` value out of a paginated `next` page URL.

    The API uses cursor pagination and returns the next page as a full URL
    in the `next` field (e.g. `.../results?cursor=abc&limit=25`). We follow
    it by reusing the cursor token, so extract just that query value here.
    Returns None when there is no next page.
    """
    if not next_url:
        return None
    from urllib.parse import urlparse, parse_qs

    try:
        values = parse_qs(urlparse(next_url).query).get("cursor")
        return values[0] if values else None
    except Exception:
        return None


class _Resource:
    """Base for resource sub-clients — holds a reference to the transport."""

    def __init__(self, transport: Transport):
        self._t = transport


class Submissions(_Resource):
    """Endpoints under `/api/v1/submissions`."""

    def create(
        self,
        *,
        fitness_func: Optional[str] = None,
        num_genes: Optional[int] = None,
        num_generations: Optional[int] = None,
        sol_per_pop: Optional[int] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        submission_type: str = "new",
        webhook_url: Optional[str] = None,
        notification_email: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        **ga_params: Any,
    ) -> Submission:
        """POST /submissions — enqueue a new optimization run.

        Extra `ga_params` are forwarded as-is so callers can pass any of
        the PyGAD knobs (`mutation_probability`, `parent_selection_type`,
        `gene_space`, …) without the SDK having to enumerate them.

        `num_generations` and `sol_per_pop` are optional: leave them unset
        to let a quick submission type apply its own server-side defaults.
        Any value you pass is forwarded as-is.
        """
        body: Dict[str, Any] = {"submission_type": submission_type}
        if num_generations is not None:
            body["num_generations"] = num_generations
        if sol_per_pop is not None:
            body["sol_per_pop"] = sol_per_pop
        if fitness_func is not None:
            body["fitness_func"] = fitness_func
        if num_genes is not None:
            body["num_genes"] = num_genes
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if webhook_url is not None:
            body["webhook_url"] = webhook_url
        if notification_email is not None:
            body["notification_email"] = notification_email
        body.update({k: v for k, v in ga_params.items() if v is not None})

        # Fill in the entry symbol for each code field, the way the website's
        # new-submission form does. The runtime requires the top-level name to
        # call and no longer guesses, so a code field sent without its
        # `<role>_entry` is rejected by the server. Detect it from the source
        # (the last top-level def/class), but never override an entry the
        # caller passed explicitly. If detection fails we leave it unset and
        # let the server return its clear "entry symbol is required" error.
        for role in CODE_ROLES:
            source = body.get(role)
            if not isinstance(source, str) or not source.strip():
                continue
            entry_key = f"{role}_entry"
            if body.get(entry_key):
                continue
            detected = _detect_entry_from_source(source)
            if detected:
                body[entry_key] = detected

        payload = self._t.request(
            "POST",
            "/submissions",
            json_body=body,
            idempotency_key=idempotency_key or Transport.make_idempotency_key(),
        )
        return Submission.from_api(payload)

    def get(self, submission_id: str) -> Submission:
        payload = self._t.request("GET", f"/submissions/{submission_id}")
        return Submission.from_api(payload)

    def list(self, *, cursor: Optional[str] = None, limit: int = 25) -> Page:
        params: Dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        payload = self._t.request("GET", "/submissions", params=params)
        items = [Submission.from_api(row) for row in payload.get("results", [])]
        return Page(items=items, next_cursor=_cursor_from_next(payload.get("next")), raw=payload)

    def iter_all(self, *, limit: int = 25) -> Iterator[Submission]:
        """Generator that follows `next_cursor` until exhausted."""
        cursor: Optional[str] = None
        while True:
            page = self.list(cursor=cursor, limit=limit)
            for item in page:
                yield item
            if not page.next_cursor:
                return
            cursor = page.next_cursor

    def delete(self, submission_id: str) -> None:
        self._t.request("DELETE", f"/submissions/{submission_id}")

    def reexecute(
        self,
        submission_id: str,
        *,
        idempotency_key: Optional[str] = None,
        **overrides: Any,
    ) -> Submission:
        """POST /submissions/{id}/reexecute — re-run with optional overrides."""
        payload = self._t.request(
            "POST",
            f"/submissions/{submission_id}/reexecute",
            json_body=overrides or None,
            idempotency_key=idempotency_key or Transport.make_idempotency_key(),
        )
        return Submission.from_api(payload)


class Results(_Resource):
    """Endpoints under `/api/v1/results`."""

    def get(self, result_id: str) -> Result:
        payload = self._t.request("GET", f"/results/{result_id}")
        return Result.from_api(payload)

    def list(
        self,
        *,
        submission_id: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 25,
    ) -> Page:
        params: Dict[str, Any] = {"limit": limit}
        if submission_id:
            params["submission_id"] = submission_id
        if cursor:
            params["cursor"] = cursor
        payload = self._t.request("GET", "/results", params=params)
        items = [Result.from_api(row) for row in payload.get("results", [])]
        return Page(items=items, next_cursor=_cursor_from_next(payload.get("next")), raw=payload)

    def update(
        self,
        result_id: str,
        *,
        name: Optional[str] = None,
        is_shared: Optional[bool] = None,
    ) -> Result:
        """PATCH /results/{id} — rename a result or change its shared flag.

        Only the fields you pass are sent, so `is_shared=False` updates just
        that flag. Returns the updated result.
        """
        body: Dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if is_shared is not None:
            body["is_shared"] = is_shared
        payload = self._t.request("PATCH", f"/results/{result_id}", json_body=body)
        return Result.from_api(payload)

    def delete(self, result_id: str) -> None:
        """DELETE /results/{id} — remove a result. The submission is untouched."""
        self._t.request("DELETE", f"/results/{result_id}")

    def continue_run(
        self,
        result_id: str,
        *,
        idempotency_key: Optional[str] = None,
        **overrides: Any,
    ) -> Submission:
        """POST /results/{id}/continue — branch a fresh run from a finished result."""
        payload = self._t.request(
            "POST",
            f"/results/{result_id}/continue",
            json_body=overrides or None,
            idempotency_key=idempotency_key or Transport.make_idempotency_key(),
        )
        return Submission.from_api(payload)

    def wait_for(
        self,
        submission_id: str,
        *,
        timeout: float = 600.0,
        poll_interval: float = 3.0,
    ) -> Result:
        """Block until the submission terminates, then return its first result.

        Polls `GET /submissions/{id}` every `poll_interval` seconds.
        Raises `vilvik.TimeoutError` if `timeout` is exceeded; raises
        `vilvik.APIError` (subclass `vilvik.exceptions.APIError`) wrapping
        the API failure if the submission ended in `failed`.
        """
        from vilvik.exceptions import APIError as _APIError

        deadline = time.monotonic() + timeout
        while True:
            sub = Submissions(self._t).get(submission_id)
            if sub.is_terminal:
                if sub.status == "failed":
                    raise _APIError(
                        status_code=0,
                        code="submission_failed",
                        message=f"Submission {submission_id} ended with status 'failed'.",
                    )
                if sub.status == "cancelled":
                    raise _APIError(
                        status_code=0,
                        code="submission_cancelled",
                        message=f"Submission {submission_id} was cancelled.",
                    )
                page = self.list(submission_id=submission_id, limit=1)
                if not page.items:
                    raise _APIError(
                        status_code=0,
                        code="result_not_found",
                        message=(
                            f"Submission {submission_id} reported '{sub.status}' "
                            "but no result row was returned."
                        ),
                    )
                return page.items[0]

            if time.monotonic() >= deadline:
                raise VilvikTimeout(
                    f"Timed out after {timeout:.0f}s waiting for submission "
                    f"{submission_id} (last status: {sub.status!r}).",
                )
            time.sleep(poll_interval)


class CodeUploads(_Resource):
    """Endpoints under `/api/v1/code-uploads`."""

    def create(self, *, content: str) -> CodeUpload:
        """Upload a code blob and get back a `code_id` to reference.

        The upload is role-agnostic. Reference it from a submission via the
        matching `<role>_id` parameter, e.g. passing the returned
        `code_id` as `fitness_func_id=...` to `submissions.create`.
        """
        payload = self._t.request(
            "POST",
            "/code-uploads",
            json_body={"content": content},
        )
        return CodeUpload.from_api(payload)

    def get(self, code_id: str) -> CodeUpload:
        return CodeUpload.from_api(self._t.request("GET", f"/code-uploads/{code_id}"))

    def list(self, *, cursor: Optional[str] = None, limit: int = 25) -> Page:
        params: Dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        payload = self._t.request("GET", "/code-uploads", params=params)
        items = [CodeUpload.from_api(row) for row in payload.get("results", [])]
        return Page(items=items, next_cursor=_cursor_from_next(payload.get("next")), raw=payload)


class Webhooks(_Resource):
    """Read-only listing of webhook subscriptions for this account.

    Mutations (create / update / delete / test / replay) currently live
    behind the dashboard's CSRF-protected endpoints rather than the
    public REST surface. They will land here once exposed under
    `/api/v1/webhooks`.
    """

    def list(self) -> List[Webhook]:
        payload = self._t.request("GET", "/webhooks")
        items = payload.get("results") if isinstance(payload, dict) else payload
        return [Webhook.from_api(row) for row in (items or [])]


class Imports(_Resource):
    """Endpoint under `/api/v1/imports` — bring a local PyGAD run into Vilvik."""

    def create(self, payload: Dict[str, Any], *, idempotency_key: Optional[str] = None) -> ImportRecord:
        data = self._t.request(
            "POST", "/imports", json_body=payload,
            idempotency_key=idempotency_key or Transport.make_idempotency_key())
        return ImportRecord.from_api(data)


class Client:
    """Top-level Vilvik client.

    Parameters
    ----------
    api_key:
        Required. Pass explicitly or set the `VILVIK_API_KEY` env var.
    base_url:
        Override for self-hosted or staging deployments.
    timeout:
        Per-request timeout in seconds.
    session:
        Pre-built `requests.Session` (useful for connection pooling or
        custom adapters / mounts during testing).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        session: Any = None,
        max_retries: int = 2,
    ):
        resolved_key = api_key or os.environ.get("VILVIK_API_KEY", "")
        if not resolved_key:
            from vilvik import _credentials
            resolved_key = _credentials.load_api_key() or ""
        self._transport = Transport(
            api_key=resolved_key,
            base_url=base_url,
            timeout=timeout,
            session=session,
            max_retries=max_retries,
        )
        self.submissions = Submissions(self._transport)
        self.results = Results(self._transport)
        self.code_uploads = CodeUploads(self._transport)
        self.webhooks = Webhooks(self._transport)
        self.imports = Imports(self._transport)

    @property
    def base_url(self) -> str:
        return self._transport.base_url

    def health(self) -> Dict[str, Any]:
        """GET /health — liveness probe; returns the raw envelope."""
        return self._transport.request("GET", "/health")
