"""Vilvik — Python SDK for the Vilvik optimization cloud API.

Quick start:

    import vilvik

    client = vilvik.Client(api_key="vlk_live_…")
    sub = client.submissions.create(
        fitness_func="def fitness_func(ga_instance, solution, idx):\\n    return -sum(s*s for s in solution)",
        num_genes=5,
        num_generations=50,
        sol_per_pop=30,
    )
    print(sub.id, sub.status_url)

    # Block until the run finishes and inspect the best fitness:
    result = client.results.wait_for(sub.id, timeout=600)
    print(result.best_fitness, result.best_solution)

For one-shot scripts, the context-managed `vilvik.run(...)` helper
combines submit + wait:

    with vilvik.run(api_key="vlk_live_…", fitness_func=fn, num_genes=5) as r:
        print(r.best_fitness)
"""

from vilvik._capture import CaptureReport
from vilvik.client import Client
from vilvik.exceptions import (
    APIError,
    AuthenticationError,
    CaptureError,
    NotFoundError,
    RateLimitError,
    TimeoutError,
    ValidationError,
    VilvikError,
)
from vilvik.models import CodeUpload, ImportRecord, Result, Submission, Webhook
from vilvik.login import login
from vilvik.run import run
from vilvik.push import push

__all__ = [
    "APIError",
    "AuthenticationError",
    "CaptureError",
    "CaptureReport",
    "Client",
    "CodeUpload",
    "ImportRecord",
    "login",
    "NotFoundError",
    "RateLimitError",
    "Result",
    "Submission",
    "TimeoutError",
    "ValidationError",
    "VilvikError",
    "Webhook",
    "push",
    "run",
]

from vilvik._version import __version__
