"""Unit tests for `vilvik.Client` and its resource sub-clients."""

from __future__ import annotations

import json
import os

import pytest

import vilvik
from vilvik.client import Client
from vilvik.models import Submission

BASE = "https://example.test/api/v1"


# --------------- Construction / config ---------------


def test_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("VILVIK_API_KEY", raising=False)
    with pytest.raises(ValueError):
        Client()


def test_client_reads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("VILVIK_API_KEY", "vlk_from_env")
    c = Client(base_url=BASE)
    # Smoke check: no exception means the env var was picked up.
    assert c.base_url == BASE


# --------------- Submissions ---------------


def test_submissions_create_round_trip(mock_api, client):
    mock_api.add(
        "POST",
        f"{BASE}/submissions",
        json={
            "id": "sub_abc",
            "status": "queued",
            "status_url": f"{BASE}/submissions/sub_abc",
            "result_url": f"{BASE}/results?submission_id=sub_abc",
            "created_at": "2026-05-18T10:00:00Z",
            "request_id": "req_1",
        },
        status=202,
    )

    sub = client.submissions.create(
        fitness_func="def fitness_func(g, s, i): return 0",
        num_genes=3,
        num_generations=10,
        sol_per_pop=20,
    )

    assert sub.id == "sub_abc"
    assert sub.status == "queued"
    assert not sub.is_terminal
    assert sub.created_at is not None

    call = mock_api.calls[0]
    assert call.request.headers["Authorization"] == f"Bearer {client._transport.api_key}"
    assert call.request.headers["Idempotency-Key"]
    body = json.loads(call.request.body)
    assert body["num_genes"] == 3
    assert body["num_generations"] == 10
    assert body["fitness_func"].startswith("def fitness_func")


def test_submissions_create_forwards_extra_ga_params(mock_api, client):
    mock_api.add(
        "POST",
        f"{BASE}/submissions",
        json={"id": "sub_x", "status": "queued"},
        status=202,
    )
    client.submissions.create(
        fitness_func="x",
        num_genes=1,
        mutation_probability=0.05,
        parent_selection_type="tournament",
    )
    body = json.loads(mock_api.calls[0].request.body)
    assert body["mutation_probability"] == 0.05
    assert body["parent_selection_type"] == "tournament"


def test_submissions_create_quick_type_omits_unset_ga_defaults(mock_api, client):
    """A quick submission type's own inputs are forwarded, and num_generations
    / sol_per_pop are NOT sent when the caller leaves them unset — so the
    service applies the quick type's own defaults."""
    mock_api.add(
        "POST",
        f"{BASE}/submissions",
        json={"id": "sub_q", "status": "queued"},
        status=202,
    )
    client.submissions.create(
        submission_type="quick_binary_subset_sum",
        integers=[3, 7, 1, 9],
        target=20,
    )
    body = json.loads(mock_api.calls[0].request.body)
    assert body["submission_type"] == "quick_binary_subset_sum"
    assert body["integers"] == [3, 7, 1, 9]
    assert body["target"] == 20
    assert "num_generations" not in body
    assert "sol_per_pop" not in body


def test_submissions_create_forwards_explicit_ga_defaults(mock_api, client):
    """Explicit num_generations / sol_per_pop are still forwarded as-is."""
    mock_api.add(
        "POST",
        f"{BASE}/submissions",
        json={"id": "sub_d", "status": "queued"},
        status=202,
    )
    client.submissions.create(
        fitness_func="def fitness_func(g, s, i): return 0",
        num_genes=4,
        num_generations=10,
        sol_per_pop=8,
    )
    body = json.loads(mock_api.calls[0].request.body)
    assert body["num_generations"] == 10
    assert body["sol_per_pop"] == 8


def test_submissions_create_auto_detects_entry_symbol(mock_api, client):
    """The entry symbol is detected from the source and sent, so callers
    don't have to repeat the function name. The runtime requires it."""
    mock_api.add("POST", f"{BASE}/submissions",
                 json={"id": "sub_e", "status": "queued"}, status=202)
    client.submissions.create(
        fitness_func="def my_fitness(g, s, i):\n    return sum(s)\n",
        num_genes=3,
    )
    body = json.loads(mock_api.calls[0].request.body)
    assert body["fitness_func_entry"] == "my_fitness"


def test_submissions_create_honors_explicit_entry_symbol(mock_api, client):
    """An explicit <role>_entry is never overridden by detection."""
    mock_api.add("POST", f"{BASE}/submissions",
                 json={"id": "sub_e2", "status": "queued"}, status=202)
    client.submissions.create(
        fitness_func="def a(g, s, i): return 0\ndef b(g, s, i): return 1\n",
        fitness_func_entry="a",
        num_genes=3,
    )
    body = json.loads(mock_api.calls[0].request.body)
    assert body["fitness_func_entry"] == "a"


def test_submissions_create_detects_entry_for_callbacks(mock_api, client):
    """Callback code fields passed as source also get their entry symbol."""
    mock_api.add("POST", f"{BASE}/submissions",
                 json={"id": "sub_e3", "status": "queued"}, status=202)
    client.submissions.create(
        fitness_func="def fitness_func(g, s, i): return 0",
        on_generation="def log_gen(ga):\n    pass\n",
        num_genes=3,
    )
    body = json.loads(mock_api.calls[0].request.body)
    assert body["fitness_func_entry"] == "fitness_func"
    assert body["on_generation_entry"] == "log_gen"


def test_submission_from_api_exposes_generated():
    """A quick submission's 202 response echoes any data the service
    generated under `generated`; it is surfaced on the model."""
    sub = Submission.from_api(
        {"id": "sub_g", "status": "queued", "generated": {"integers": [1, 2, 3]}}
    )
    assert sub.generated == {"integers": [1, 2, 3]}


def test_submission_from_api_generated_defaults_to_empty():
    """A response without `generated` yields an empty dict, not None."""
    sub = Submission.from_api({"id": "sub_n", "status": "queued"})
    assert sub.generated == {}


def test_submissions_get(mock_api, client):
    mock_api.add(
        "GET",
        f"{BASE}/submissions/sub_abc",
        json={"id": "sub_abc", "status": "succeeded"},
    )
    sub = client.submissions.get("sub_abc")
    assert sub.is_terminal
    assert sub.status == "succeeded"


def test_submissions_list_and_iter_all(mock_api, client):
    mock_api.add(
        "GET",
        f"{BASE}/submissions",
        json={
            "results": [
                {"id": "a", "status": "queued"},
                {"id": "b", "status": "running"},
            ],
            "next": f"{BASE}/submissions?cursor=cur_2&limit=25",
        },
    )
    mock_api.add(
        "GET",
        f"{BASE}/submissions",
        json={
            "results": [{"id": "c", "status": "succeeded"}],
            "next": None,
        },
    )
    ids = [s.id for s in client.submissions.iter_all()]
    assert ids == ["a", "b", "c"]


def test_submissions_reexecute_sends_overrides(mock_api, client):
    mock_api.add(
        "POST",
        f"{BASE}/submissions/sub_abc/reexecute",
        json={"id": "sub_def", "status": "queued"},
        status=202,
    )
    client.submissions.reexecute("sub_abc", mutation_probability=0.2)
    body = json.loads(mock_api.calls[0].request.body)
    assert body == {"mutation_probability": 0.2}


def test_submissions_delete(mock_api, client):
    mock_api.add("DELETE", f"{BASE}/submissions/sub_abc", status=204)
    # Must not raise.
    assert client.submissions.delete("sub_abc") is None


# --------------- Results ---------------


def test_results_get(mock_api, client):
    mock_api.add(
        "GET",
        f"{BASE}/results/res_1",
        json={
            "id": "res_1",
            "submission_id": "sub_abc",
            "best_solution_fitness": "-0.0123",
            "best_solution": [1, 2, 3],
            "generations_completed": 100,
        },
    )
    r = client.results.get("res_1")
    assert r.best_fitness == pytest.approx(-0.0123)
    assert r.best_solution == [1, 2, 3]
    assert r.num_generations_ran == 100


def test_results_continue_run(mock_api, client):
    mock_api.add(
        "POST",
        f"{BASE}/results/res_1/continue",
        json={"id": "sub_child", "status": "queued"},
        status=202,
    )
    child = client.results.continue_run("res_1", sol_per_pop=200)
    assert child.id == "sub_child"
    body = json.loads(mock_api.calls[0].request.body)
    assert body == {"sol_per_pop": 200}


def test_results_delete(mock_api, client):
    mock_api.add("DELETE", f"{BASE}/results/res_1", status=204)
    # Must not raise and returns None on 204.
    assert client.results.delete("res_1") is None


def test_results_update_sends_patch_and_returns_result(mock_api, client):
    mock_api.add(
        "PATCH",
        f"{BASE}/results/res_1",
        json={
            "id": "res_1",
            "submission_id": "sub_abc",
            "name": "renamed result",
            "is_shared": True,
        },
    )
    r = client.results.update("res_1", name="renamed result", is_shared=True)
    assert mock_api.calls[0].request.method == "PATCH"
    body = json.loads(mock_api.calls[0].request.body)
    assert body == {"name": "renamed result", "is_shared": True}
    assert r.name == "renamed result"
    assert r.is_shared is True


def test_results_update_sends_only_provided_fields(mock_api, client):
    """Partial update: passing only is_shared=False must send just that key
    (False is a real value, not 'unset')."""
    mock_api.add(
        "PATCH",
        f"{BASE}/results/res_1",
        json={"id": "res_1", "submission_id": "sub_abc", "is_shared": False},
    )
    client.results.update("res_1", is_shared=False)
    body = json.loads(mock_api.calls[0].request.body)
    assert body == {"is_shared": False}


def test_wait_for_returns_result_when_submission_succeeds(mock_api, client, monkeypatch):
    monkeypatch.setattr("vilvik.client.time.sleep", lambda *_a, **_k: None)
    # First poll: still running. Second poll: succeeded. Then list returns one row.
    mock_api.add(
        "GET",
        f"{BASE}/submissions/sub_abc",
        json={"id": "sub_abc", "status": "running"},
    )
    mock_api.add(
        "GET",
        f"{BASE}/submissions/sub_abc",
        json={"id": "sub_abc", "status": "succeeded"},
    )
    mock_api.add(
        "GET",
        f"{BASE}/results",
        json={
            "results": [
                {"id": "res_1", "submission_id": "sub_abc", "best_solution_fitness": "7.0"},
            ],
            "next": None,
        },
    )
    r = client.results.wait_for("sub_abc", timeout=5, poll_interval=0)
    assert r.best_fitness == 7.0


def test_wait_for_raises_on_failed_submission(mock_api, client, monkeypatch):
    monkeypatch.setattr("vilvik.client.time.sleep", lambda *_a, **_k: None)
    mock_api.add(
        "GET",
        f"{BASE}/submissions/sub_bad",
        json={"id": "sub_bad", "status": "failed"},
    )
    with pytest.raises(vilvik.APIError) as info:
        client.results.wait_for("sub_bad", timeout=5, poll_interval=0)
    assert info.value.code == "submission_failed"


def test_wait_for_times_out(mock_api, client, monkeypatch):
    # Two stubbed responses, both "running" — the deadline will trigger first.
    monkeypatch.setattr("vilvik.client.time.sleep", lambda *_a, **_k: None)
    # responses replays the last match if exhausted; we set monotonic to
    # walk past the deadline on the second call.
    times = iter([0.0, 0.0, 999.0])
    monkeypatch.setattr("vilvik.client.time.monotonic", lambda: next(times))
    mock_api.add(
        "GET",
        f"{BASE}/submissions/sub_x",
        json={"id": "sub_x", "status": "running"},
    )
    with pytest.raises(vilvik.TimeoutError):
        client.results.wait_for("sub_x", timeout=1, poll_interval=0)


# --------------- Code uploads & webhooks ---------------


def test_code_upload_create(mock_api, client):
    mock_api.add(
        "POST",
        f"{BASE}/code-uploads",
        json={"code_id": "code_1", "content_size": 42, "is_expired": False},
        status=201,
    )
    blob = client.code_uploads.create(
        content="def fitness_func(g, s, i): return 0",
    )
    assert blob.code_id == "code_1"
    assert blob.content_size == 42
    # The request sends the source under `content`, matching the REST API.
    body = json.loads(mock_api.calls[0].request.body)
    assert body == {"content": "def fitness_func(g, s, i): return 0"}


def test_code_upload_referenced_in_submission(mock_api, client):
    """An uploaded blob is referenced by `<role>_id`, using its code_id."""
    mock_api.add("POST", f"{BASE}/submissions",
                 json={"id": "sub_ref", "status": "queued"}, status=202)
    client.submissions.create(
        fitness_func_id="code_1",
        fitness_func_entry="fitness_func",
        num_genes=3,
    )
    body = json.loads(mock_api.calls[0].request.body)
    assert body["fitness_func_id"] == "code_1"


def test_webhooks_list(mock_api, client):
    mock_api.add(
        "GET",
        f"{BASE}/webhooks",
        json={
            "results": [
                {"id": "wh_1", "url": "https://example.test/hook",
                 "event_types": ["submission.completed"]},
            ],
        },
    )
    hooks = client.webhooks.list()
    assert hooks[0].id == "wh_1"
    assert "submission.completed" in hooks[0].event_types


# --------------- Error translation ---------------


def test_authentication_error_translation(mock_api, client):
    mock_api.add(
        "GET",
        f"{BASE}/submissions/sub_abc",
        json={"error": {"code": "invalid_key", "message": "bad key",
                        "request_id": "req_z"}},
        status=401,
    )
    with pytest.raises(vilvik.AuthenticationError) as info:
        client.submissions.get("sub_abc")
    assert info.value.code == "invalid_key"
    assert info.value.request_id == "req_z"
    assert info.value.status_code == 401


def test_rate_limit_error_picks_up_retry_after(mock_api, client):
    mock_api.add(
        "GET",
        f"{BASE}/submissions",
        json={"error": {"code": "rate_limited", "message": "slow down"}},
        status=429,
        headers={"Retry-After": "7"},
    )
    with pytest.raises(vilvik.RateLimitError) as info:
        client.submissions.list()
    assert info.value.retry_after == 7


def test_not_found_error(mock_api, client):
    mock_api.add(
        "GET",
        f"{BASE}/submissions/ghost",
        json={"error": {"code": "not_found", "message": "missing"}},
        status=404,
    )
    with pytest.raises(vilvik.NotFoundError):
        client.submissions.get("ghost")


def test_validation_error(mock_api, client):
    mock_api.add(
        "POST",
        f"{BASE}/submissions",
        json={"error": {"code": "validation_failed",
                        "message": "num_genes is required"}},
        status=400,
    )
    with pytest.raises(vilvik.ValidationError):
        client.submissions.create(num_generations=10)


def test_generic_api_error_for_5xx(mock_api, client):
    mock_api.add(
        "GET",
        f"{BASE}/submissions/sub_abc",
        json={"error": {"code": "upstream", "message": "boom"}},
        status=502,
    )
    with pytest.raises(vilvik.APIError) as info:
        client.submissions.get("sub_abc")
    assert info.value.status_code == 502
    # Not auth/notfound/validation/ratelimit.
    assert not isinstance(info.value, vilvik.AuthenticationError)
    assert not isinstance(info.value, vilvik.NotFoundError)
    assert not isinstance(info.value, vilvik.ValidationError)
    assert not isinstance(info.value, vilvik.RateLimitError)


# --------------- run() context manager ---------------


def test_run_context_manager_yields_result(mock_api, monkeypatch):
    monkeypatch.setattr("vilvik.client.time.sleep", lambda *_a, **_k: None)
    monkeypatch.setenv("VILVIK_API_KEY", "vlk_test_env")
    mock_api.add(
        "POST",
        f"{BASE}/submissions",
        json={"id": "sub_quick", "status": "queued"},
        status=202,
    )
    mock_api.add(
        "GET",
        f"{BASE}/submissions/sub_quick",
        json={"id": "sub_quick", "status": "succeeded"},
    )
    mock_api.add(
        "GET",
        f"{BASE}/results",
        json={
            "results": [{"id": "res_q", "submission_id": "sub_quick",
                      "best_solution_fitness": "1.5"}],
            "next": None,
        },
    )
    # The submission lookup at __exit__ time finds a terminal run, so no
    # DELETE is issued — `assert_all_requests_are_fired=False` keeps the
    # mock from complaining about unused matchers.
    mock_api.add(
        "GET",
        f"{BASE}/submissions/sub_quick",
        json={"id": "sub_quick", "status": "succeeded"},
    )

    with vilvik.run(
        base_url=BASE,
        fitness_func="x",
        num_genes=2,
        poll_interval=0,
        timeout=5,
    ) as result:
        assert result.id == "res_q"
        assert result.best_fitness == 1.5
