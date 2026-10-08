"""Exercise the public SDK with real, completed PyGAD instances.

HTTP alone is mocked: source capture, parameter/result extraction, JSON
encoding, response models and reconstruction use the actual libraries.
"""
import copy
import json

import numpy as np
import pytest

pygad = pytest.importorskip("pygad", reason="install the compatibility test extra")

import vilvik

BASE = "https://example.test/api/v1"


def fitness(ga_instance, solution, solution_idx):
    return float(np.sum(solution))


def multi_fitness(ga_instance, solution, solution_idx):
    return [float(sum(solution)), -float(sum(value * value for value in solution))]


def on_start(ga_instance):
    ga_instance.exported_events = ["start"]


def on_fitness(ga_instance, population_fitness):
    ga_instance.exported_events.append("fitness")


def on_parents(ga_instance, selected_parents):
    ga_instance.exported_events.append("parents")


def on_crossover(ga_instance, offspring):
    ga_instance.exported_events.append("crossover")


def on_mutation(ga_instance, offspring):
    ga_instance.exported_events.append("mutation")


def on_generation(ga_instance):
    ga_instance.exported_events.append("generation")


def on_stop(ga_instance, last_population_fitness):
    ga_instance.exported_events.append("stop")


def make_ga(**overrides):
    options = dict(num_generations=2, num_parents_mating=2, sol_per_pop=4,
                   num_genes=3, fitness_func=fitness, random_seed=17,
                   mutation_num_genes=1, suppress_warnings=True)
    options.update(overrides)
    return pygad.GA(**options)


def push_payload(ga, mock_api, client, **overrides):
    mock_api.add("POST", BASE + "/imports", status=201,
                 json={"id": "imported", "result_id": "result", "result_url": BASE + "/results/result"})
    record = vilvik.push(ga, client=client, **overrides)
    assert isinstance(record, vilvik.ImportRecord)
    assert record.id == "imported"
    assert record.result_id == "result"
    request = mock_api.calls[-1].request
    assert request.headers.get("Idempotency-Key")
    payload = json.loads(request.body)
    json.dumps(payload, allow_nan=False)
    assert payload["origin"]["client"] == "sdk"
    assert payload["origin"]["sdk_version"] == vilvik.__version__
    return payload


def restore(payload):
    """Rebuild a GA from the wire contract, independently of SDK internals."""
    params = copy.deepcopy(payload["ga_parameters"])
    for role, source in payload["code"].items():
        if role.endswith("_entry"):
            continue
        namespace = {}
        exec(compile(source, "<imported-" + role + ">", "exec"), namespace)
        params[role] = namespace[payload["code"][role + "_entry"]]
    expression = params.pop("custom_gene_type", params["gene_type"])
    params["gene_type"] = eval(expression, {"__builtins__": {}, "float": float,
                                           "int": int, "numpy": np})
    params.pop("sol_per_pop")
    params.pop("num_genes")
    params["initial_population"] = payload["result"]["population"]
    params["num_generations"] = 1
    params["suppress_warnings"] = True
    return pygad.GA(**params)


@pytest.mark.parametrize("gene_type", [float, int, np.float32, np.float64, np.int32,
                                     [float, 2], [int, [float, 2], np.float32]])
def test_real_gene_types_population_and_results_round_trip(gene_type, mock_api, client):
    ga = make_ga(gene_type=gene_type)
    ga.run()
    before = ga.population.copy()
    payload = push_payload(ga, mock_api, client)
    result = payload["result"]
    best, best_fitness, index = ga.best_solution()
    np.testing.assert_allclose(result["best_solution"], np.asarray(best, dtype=float))
    np.testing.assert_allclose(result["population"], np.asarray(before, dtype=float))
    np.testing.assert_allclose(result["last_generation_fitness"], ga.last_generation_fitness)
    np.testing.assert_allclose(result["best_solutions_fitness"], ga.best_solutions_fitness)
    assert result["best_solution_fitness"] == pytest.approx(float(best_fitness))
    assert result["best_solution_idx"] == index
    assert result["generations_completed"] == ga.generations_completed
    assert result["best_solution_generation"] == ga.best_solution_generation
    assert result["gene_type_single"] is ga.gene_type_single
    np.testing.assert_array_equal(ga.population, before)
    continued = restore(payload)
    np.testing.assert_allclose(np.asarray(continued.population, dtype=float), np.asarray(before, dtype=float))
    assert continued.gene_type_single is ga.gene_type_single
    continued.run()
    assert continued.generations_completed == 1
    assert np.isfinite(continued.best_solution()[1])


@pytest.mark.parametrize("options,control", [
    ({"mutation_num_genes": None}, "mutation_num_genes"),
    ({"mutation_probability": 0.3}, "mutation_probability"),
    ({"mutation_type": "adaptive", "mutation_probability": [0.6, 0.2], "mutation_num_genes": [2, 1]}, "mutation_probability"),
    ({"mutation_type": "adaptive", "mutation_num_genes": [2, 1]}, "mutation_num_genes"),
    ({"mutation_type": "adaptive", "mutation_num_genes": None, "mutation_percent_genes": [50, 25]}, "mutation_num_genes"),
])
def test_mutation_precedence_produces_runnable_parameters(options, control, mock_api, client):
    ga = make_ga(**options)
    ga.run()
    payload = push_payload(ga, mock_api, client)
    controls = {"mutation_probability", "mutation_percent_genes", "mutation_num_genes"}
    assert controls.intersection(payload["ga_parameters"]) == {control}
    reconstructed = restore(payload)
    reconstructed.run()
    assert reconstructed.generations_completed == 1


@pytest.mark.parametrize("stops", [["saturate_5"], ["reach_100000"], ["saturate_5", "reach_100000"]])
def test_parsed_stop_criteria_export_as_constructor_inputs(stops, mock_api, client):
    ga = make_ga(stop_criteria=stops)
    ga.run()
    payload = push_payload(ga, mock_api, client)
    assert len(payload["ga_parameters"]["stop_criteria"]) == len(stops)
    assert all(isinstance(stop, str) for stop in payload["ga_parameters"]["stop_criteria"])
    continued = restore(payload)
    continued.run()
    assert continued.generations_completed == 1


def test_multi_objective_results_and_stop_criteria(mock_api, client):
    ga = make_ga(fitness_func=multi_fitness, parent_selection_type="nsga2",
                 stop_criteria=["reach_100000_100000", "saturate_5"])
    ga.run()
    payload = push_payload(ga, mock_api, client)
    np.testing.assert_allclose(payload["result"]["best_solution_fitness"], ga.best_solution()[1])
    assert np.asarray(payload["result"]["last_generation_fitness"]).shape == (4, 2)
    continued = restore(payload)
    continued.run()
    assert continued.last_generation_fitness.shape == (4, 2)


def test_all_lifecycle_callbacks_remain_executable(mock_api, client):
    callbacks = dict(on_start=on_start, on_fitness=on_fitness, on_parents=on_parents,
                     on_crossover=on_crossover, on_mutation=on_mutation,
                     on_generation=on_generation, on_stop=on_stop)
    ga = make_ga(**callbacks)
    ga.run()
    original_events = list(ga.exported_events)
    payload = push_payload(ga, mock_api, client)
    assert set(callbacks).issubset(payload["code"])
    continued = restore(payload)
    continued.run()
    assert continued.exported_events[0] == "start"
    assert continued.exported_events[-1] == "stop"
    assert set(continued.exported_events) == {"start", "fitness", "parents", "crossover", "mutation", "generation", "stop"}
    assert ga.exported_events == original_events


def test_per_gene_space_numpy_values_and_population_opt_out(mock_api, client):
    ga = make_ga(gene_space=[np.array([1, 2, 3]), {"low": 0, "high": 2, "step": 0.25}, [0, 1]])
    ga.run()
    payload = push_payload(ga, mock_api, client, include_population=False)
    assert "population" not in payload["result"]
    assert payload["ga_parameters"]["gene_space"][0] == [1, 2, 3]
    assert payload["result"]["generations_completed"] == 2


def test_real_ga_dry_run_and_capture_override(mock_api, client):
    ga = make_ga(fitness_func=lambda ga, solution, index: float(sum(solution)))
    ga.run()
    assert not vilvik.push(ga, dry_run=True).ok()
    with pytest.raises(vilvik.CaptureError):
        vilvik.push(ga, client=client)
    assert len(mock_api.calls) == 0
    payload = push_payload(ga, mock_api, client,
                           fitness_source="def replacement(ga, solution, index):\n    return float(sum(solution))\n")
    assert payload["code"]["fitness_func_entry"] == "replacement"
    restore(payload).run()


@pytest.mark.skipif(pygad.__version__ == "3.6.0", reason="PyGAD 3.6.0 predates the push_to_vilvik wrapper; vilvik.push is tested above")
def test_captured_source_supports_current_pygad_wrapper(mock_api, client):
    ga = make_ga()
    ga.run()
    mock_api.add("POST", BASE + "/imports", status=201, json={"id": "wrapper", "result_id": "result"})
    record = ga.push_to_vilvik(client=client)
    assert record.id == "wrapper"
    payload = json.loads(mock_api.calls[0].request.body)
    assert payload["origin"]["client"] == "pygad_wrapper"
    assert payload["origin"]["pygad_version"] == pygad.__version__
    restore(payload).run()
