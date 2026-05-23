"""Tests for vilvik.push() — the one-call local-GA import orchestrator."""
import json
from types import SimpleNamespace
import pytest
import vilvik
from vilvik.exceptions import CaptureError

BASE = "https://example.test/api/v1"


def module_fitness(ga_instance, solution, solution_idx):
    return 0.0


class _FakeArray:
    def __init__(self, d): self._d = d
    def tolist(self): return self._d


def _ga():
    ga = SimpleNamespace(
        num_generations=5, sol_per_pop=4, num_parents_mating=2, num_genes=3,
        fitness_func=module_fitness, best_solutions_fitness=[0.1, 0.9],
        generations_completed=5, best_solution_generation=3,
        population=_FakeArray([[1.0, 2.0, 3.0]]))
    ga.best_solution = lambda *a, **k: (_FakeArray([1.0, 2.0, 3.0]), 0.9, 0)
    return ga


def test_dry_run_returns_report_no_network():
    report = vilvik.push(_ga(), api_key="vlk_test_x", base_url=BASE, dry_run=True)
    assert report.ok()
    assert report.role("fitness_func").entry == "module_fitness"


def test_push_posts_payload(mock_api, client):
    mock_api.add("POST", f"{BASE}/imports",
                 json={"id": "sub_x", "result_id": "res_y",
                       "result_url": f"{BASE}/results/res_y"}, status=201)
    rec = vilvik.push(_ga(), client=client, name="local run")
    assert rec.id == "sub_x"
    body = json.loads(mock_api.calls[0].request.body)
    assert body["name"] == "local run"
    assert body["ga_parameters"]["num_generations"] == 5
    assert "def module_fitness" in body["code"]["fitness_func"]
    assert body["code"]["fitness_func_entry"] == "module_fitness"
    assert body["result"]["best_solution"] == [1.0, 2.0, 3.0]
    assert body["result"]["population"] == [[1.0, 2.0, 3.0]]
    assert body["origin"]["client"] == "sdk"
    assert body["origin"]["sdk_version"] == vilvik.__version__
    assert "python_version" in body["origin"]


def test_push_unresolved_raises_capture_error(client):
    ga = _ga(); ga.fitness_func = lambda g, s, i: 0.0  # un-capturable, no override
    with pytest.raises(CaptureError) as exc:
        vilvik.push(ga, client=client)
    assert "fitness" in str(exc.value).lower()


def test_push_preamble_prepended_into_code_block(mock_api, client):
    mock_api.add("POST", f"{BASE}/imports",
                 json={"id": "s", "result_id": "r", "result_url": "u"}, status=201)
    vilvik.push(_ga(), client=client, preamble="import numpy as np")
    body = json.loads(mock_api.calls[0].request.body)
    assert body["code"]["fitness_func"].startswith("import numpy as np")


def test_push_does_not_print_to_stdout(mock_api, client, capsys):
    mock_api.add("POST", f"{BASE}/imports",
                 json={"id": "s", "result_id": "r", "result_url": "u"}, status=201)
    rec = vilvik.push(_ga(), client=client)
    assert rec.id == "s"
    out = capsys.readouterr().out
    assert "capture report" not in out.lower()
    assert out == ""  # nothing printed to stdout by the library


def test_push_origin_overrides(mock_api, client):
    import json as _json
    mock_api.add("POST", f"{BASE}/imports",
                 json={"id": "s", "result_id": "r", "result_url": "u"}, status=201)
    vilvik.push(_ga(), client=client,
                origin_overrides={"client": "pygad_wrapper", "pygad_version": "3.6.0"})
    body = _json.loads(mock_api.calls[0].request.body)
    assert body["origin"]["client"] == "pygad_wrapper"
    assert body["origin"]["pygad_version"] == "3.6.0"
    assert "sdk_version" in body["origin"]
    assert "python_version" in body["origin"]
