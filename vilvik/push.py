"""High-level helper: bring a local pygad.GA into Vilvik in one call."""
from __future__ import annotations

import logging
import platform
from typing import Any, Dict, Optional

logger = logging.getLogger("vilvik")

from vilvik import _capture, _extract
from vilvik.client import Client
from vilvik.exceptions import CaptureError


def _code_payload(report: "_capture.CaptureReport") -> Dict[str, str]:
    """Merge the preamble into each resolved code block; add entry names.

    The server stores each code field separately and execs it (no preamble
    field), so imports/helpers are prepended into every block.
    """
    code: Dict[str, str] = {}
    preamble = (report.preamble or "").strip()
    for r in report.roles:
        if r.provenance in ("auto", "override") and r.source:
            code[r.role] = f"{preamble}\n\n{r.source}" if preamble else r.source
            if r.entry:
                code[f"{r.role}_entry"] = r.entry
    return code


def push(
    ga: Any,
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    client: Optional[Client] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    fitness_func: Any = None,
    fitness_source: Optional[str] = None,
    fitness_entry: Optional[str] = None,
    callbacks: Optional[Dict[str, Any]] = None,
    preamble: Optional[str] = None,
    include_population: bool = True,
    dry_run: bool = False,
    origin_overrides: Optional[Dict[str, Any]] = None,
) -> Any:
    """Import a local ``pygad.GA`` run into Vilvik as an editable record.

    Returns a ``CaptureReport`` when ``dry_run=True`` (no network), else an
    ``ImportRecord``. Raises ``CaptureError`` if the fitness function (or a
    callback) cannot be captured and was not passed explicitly.
    """
    report = _capture.capture_code(
        ga, fitness_func=fitness_func, fitness_source=fitness_source,
        fitness_entry=fitness_entry, callbacks=callbacks, preamble=preamble)

    if dry_run:
        return report
    if not report.ok():
        raise CaptureError(str(report))

    import vilvik as _vilvik
    origin = {
        "client": "sdk",
        "sdk_version": _vilvik.__version__,
        "python_version": platform.python_version(),
    }
    if origin_overrides:
        origin.update(origin_overrides)
    payload: Dict[str, Any] = {
        "ga_parameters": _extract.extract_ga_parameters(ga),
        "code": _code_payload(report),
        "result": _extract.extract_result(ga, include_population=include_population),
        "origin": origin,
    }
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description

    cli = client
    if cli is None:
        kwargs: Dict[str, Any] = {}
        if base_url is not None:
            kwargs["base_url"] = base_url
        cli = Client(api_key=api_key, **kwargs)
    record = cli.imports.create(payload)
    logger.info("vilvik import complete:\n%s", report)
    return record
