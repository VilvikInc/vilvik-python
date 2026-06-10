"""Context-managed one-shot helper: `vilvik.run(...)`.

Lets a script submit a run and block until it finishes in a single
expression — the workflow most users actually want in a Jupyter cell:

    with vilvik.run(fitness_func=fn, num_genes=5, num_generations=50,
                    sol_per_pop=10, num_parents_mating=4) as result:
        print(result.best_fitness)

The context manager handles client construction, submission, and the
polling loop. On exit (success or exception) it tries to cancel the run
if it has not yet reached a terminal state, so a Ctrl-C in a notebook
does not leave a hot run on the server.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Optional

from vilvik.client import Client
from vilvik.exceptions import APIError


@contextmanager
def run(
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 600.0,
    poll_interval: float = 3.0,
    **submission_kwargs: Any,
) -> Iterator[Any]:
    """Submit a run, block on completion, and yield the resulting `Result`.

    Any keyword not consumed by the context manager itself is forwarded
    to `Client.submissions.create(...)` — so `fitness_func`, `num_genes`,
    `num_generations`, `sol_per_pop`, plus any extra PyGAD params all
    work here directly.
    """
    client_kwargs: dict = {}
    if api_key is not None:
        client_kwargs["api_key"] = api_key
    if base_url is not None:
        client_kwargs["base_url"] = base_url
    client = Client(**client_kwargs)

    submission = client.submissions.create(**submission_kwargs)
    try:
        result = client.results.wait_for(
            submission.id,
            timeout=timeout,
            poll_interval=poll_interval,
        )
        yield result
    finally:
        # Best-effort cancel if the user exited the block early (Ctrl-C,
        # exception, etc.) before the run had a chance to finish. The
        # API does not currently expose a public cancel endpoint, so we
        # try DELETE — failures are silently swallowed because the
        # submission may already be terminal.
        try:
            latest = client.submissions.get(submission.id)
            if not latest.is_terminal:
                client.submissions.delete(submission.id)
        except APIError:
            pass
