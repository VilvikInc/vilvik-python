"""Typed dataclasses for the public surface of the Vilvik API.

Each `from_api()` classmethod is lenient on missing keys so a server-side
addition does not break older SDK builds. New keys not yet modelled here
are preserved on `raw` for forward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


def _parse_dt(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp; return None when missing or malformed."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


@dataclass
class Submission:
    """A queued, running, or completed optimization run."""

    id: str
    status: str
    status_url: str = ""
    result_url: str = ""
    name: Optional[str] = None
    description: Optional[str] = None
    submission_type: Optional[str] = None
    created_at: Optional[datetime] = None
    request_id: Optional[str] = None
    generated: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        """True once the server-side run has reached a final state.

        The terminal statuses are `succeeded`, `failed`, and `cancelled`;
        `queued` and `running` are not.
        """
        return self.status in {"succeeded", "failed", "cancelled"}

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "Submission":
        return cls(
            id=str(data.get("id", "")),
            status=str(data.get("status", "")),
            status_url=str(data.get("status_url", "") or ""),
            result_url=str(data.get("result_url", "") or ""),
            name=data.get("name"),
            description=data.get("description"),
            submission_type=data.get("submission_type"),
            created_at=_parse_dt(data.get("created_at")),
            request_id=data.get("request_id"),
            generated=data.get("generated") or {},
            raw=dict(data),
        )


@dataclass
class Result:
    """The outcome row associated with a finished submission."""

    id: str
    submission_id: str
    name: Optional[str] = None
    is_shared: Optional[bool] = None
    best_fitness: Optional[float] = None
    best_solution: Optional[List[Any]] = None
    num_generations_ran: Optional[int] = None
    stopped_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "Result":
        # The API names the fitness `best_solution_fitness` and the
        # generation count `generations_completed`; accept the older
        # `best_fitness` / `num_generations_ran` too for forward safety.
        # best_solution_fitness is a string (a number, or a JSON list for
        # multi-objective runs), so coerce it back to a number/list.
        raw_fitness = data.get("best_solution_fitness", data.get("best_fitness"))
        best_fitness: Any = raw_fitness
        if isinstance(raw_fitness, str):
            try:
                best_fitness = float(raw_fitness)
            except ValueError:
                try:
                    import json as _json

                    best_fitness = _json.loads(raw_fitness)
                except Exception:
                    best_fitness = raw_fitness
        return cls(
            id=str(data.get("id", "")),
            submission_id=str(data.get("submission_id", "")),
            name=data.get("name"),
            is_shared=data.get("is_shared"),
            best_fitness=best_fitness,
            best_solution=data.get("best_solution"),
            num_generations_ran=data.get("generations_completed", data.get("num_generations_ran")),
            stopped_reason=data.get("stopped_reason"),
            created_at=_parse_dt(data.get("created_at")),
            raw=dict(data),
        )


@dataclass
class CodeUpload:
    """A reusable code blob that submissions can reference by id.

    Uploads are role-agnostic: the server stores the source and returns a
    `code_id`. You choose which role it fills when you reference it from a
    submission, e.g. `fitness_func_id=upload.code_id`.
    """

    code_id: str
    content: Optional[str] = None
    content_size: Optional[int] = None
    content_sha256: Optional[str] = None
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_expired: Optional[bool] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "CodeUpload":
        return cls(
            code_id=str(data.get("code_id", "")),
            content=data.get("content"),
            content_size=data.get("content_size"),
            content_sha256=data.get("content_sha256"),
            created_at=_parse_dt(data.get("created_at")),
            expires_at=_parse_dt(data.get("expires_at")),
            is_expired=data.get("is_expired"),
            raw=dict(data),
        )


@dataclass
class Webhook:
    """A user-configured webhook endpoint."""

    id: str
    url: str = ""
    event_types: List[str] = field(default_factory=list)
    is_active: bool = True
    created_at: Optional[datetime] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "Webhook":
        return cls(
            id=str(data.get("id", "")),
            url=str(data.get("url", "") or ""),
            event_types=list(data.get("event_types") or []),
            is_active=bool(data.get("is_active", True)),
            created_at=_parse_dt(data.get("created_at")),
            raw=dict(data),
        )


@dataclass
class ImportRecord:
    """The record created by POST /imports (an editable, continuable run)."""

    id: str
    result_id: str = ""
    result_url: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "ImportRecord":
        return cls(
            id=str(data.get("id", "")),
            result_id=str(data.get("result_id", "") or ""),
            result_url=str(data.get("result_url", "") or ""),
            raw=dict(data),
        )


@dataclass
class Page:
    """One page of a cursor-paginated list response."""

    items: List[Any]
    next_cursor: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)
