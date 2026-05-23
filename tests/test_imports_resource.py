import json
from vilvik.models import ImportRecord

BASE = "https://example.test/api/v1"


def test_import_record_from_api():
    rec = ImportRecord.from_api({"id": "sub_x", "result_id": "res_y",
                                 "result_url": "https://v/api/v1/results/res_y"})
    assert rec.id == "sub_x" and rec.result_id == "res_y"
    assert rec.result_url.endswith("res_y")


def test_imports_create_round_trip(mock_api, client):
    mock_api.add("POST", f"{BASE}/imports",
                 json={"id": "sub_x", "result_id": "res_y",
                       "result_url": f"{BASE}/results/res_y"}, status=201)
    rec = client.imports.create({"name": "x", "ga_parameters": {"num_generations": 1},
                                 "code": {"fitness_func": "def fitness_func(g,s,i): return 0",
                                          "fitness_func_entry": "fitness_func"},
                                 "result": {"best_solution": [1.0], "best_solution_fitness": 0.0,
                                            "generations_completed": 1}})
    assert rec.id == "sub_x"
    body = json.loads(mock_api.calls[0].request.body)
    assert body["ga_parameters"]["num_generations"] == 1
    assert mock_api.calls[0].request.headers["Idempotency-Key"]
