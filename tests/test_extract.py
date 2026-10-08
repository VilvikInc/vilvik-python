from types import SimpleNamespace
from vilvik import _extract


class _FakeArray:
    """Minimal numpy-like: has tolist()."""
    def __init__(self, data): self._d = data
    def tolist(self): return self._d


def _fake_ga():
    ga = SimpleNamespace(
        num_generations=10, sol_per_pop=8, num_parents_mating=4, num_genes=3,
        gene_type=float, mutation_type="random", parent_selection_type="sss",
        best_solutions_fitness=[0.1, 0.5, 0.9],
        generations_completed=10, best_solution_generation=7,
        population=_FakeArray([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]),
        last_generation_fitness=_FakeArray([0.2, 0.9]),
    )
    ga.best_solution = lambda *a, **k: (_FakeArray([1.0, 2.0, 3.0]), 0.9, 0)
    return ga


def test_extract_ga_parameters_basic():
    p = _extract.extract_ga_parameters(_fake_ga())
    assert p["num_generations"] == 10
    assert p["sol_per_pop"] == 8
    assert p["mutation_type"] == "random"
    assert "gene_type" not in p or isinstance(p["gene_type"], str)


def test_extract_ga_parameters_stringifies_type():
    p = _extract.extract_ga_parameters(_fake_ga())
    # gene_type=float should become "float" (a type object must never leak).
    assert p.get("gene_type") == "float"


def test_extract_ga_parameters_skips_callable_operators():
    ga = _fake_ga()
    ga.mutation_type = lambda *a, **k: None  # custom operator callable
    p = _extract.extract_ga_parameters(ga)
    assert "mutation_type" not in p  # callable knobs can't transfer as strings


def test_extract_result_basic():
    r = _extract.extract_result(_fake_ga(), include_population=True)
    assert r["best_solution"] == [1.0, 2.0, 3.0]
    assert r["best_solution_idx"] == 0
    assert r["best_solution_fitness"] == 0.9
    assert r["best_solutions_fitness"] == [0.1, 0.5, 0.9]
    assert r["generations_completed"] == 10
    assert r["best_solution_generation"] == 7
    assert r["population"] == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
    assert r["last_generation_fitness"] == [0.2, 0.9]


def test_extract_result_excludes_population_when_disabled():
    r = _extract.extract_result(_fake_ga(), include_population=False)
    assert "population" not in r


def test_normalized_default_gene_type_is_json_serializable():
    import json
    ga = _fake_ga(); ga.gene_type = [float, None]; ga.gene_type_single = True
    payload = _extract.extract_ga_parameters(ga)
    assert payload["gene_type"] == "float"
    json.dumps(payload)


def test_normalized_gene_type_preserves_precision_and_mixed_types():
    ga = _fake_ga(); ga.gene_type = [float, 2]; ga.gene_type_single = True
    payload = _extract.extract_ga_parameters(ga)
    assert payload["gene_type"] == "custom"
    assert payload["custom_gene_type"] == "[float, 2]"
    ga.gene_type = [[int, None], [float, 2]]; ga.gene_type_single = False
    assert _extract.extract_ga_parameters(ga)["custom_gene_type"] == "[[int, None], [float, 2]]"


def test_derived_mutation_knobs_and_parsed_stop_criteria():
    ga = _fake_ga()
    ga.mutation_percent_genes = 10; ga.mutation_num_genes = 1
    ga.stop_criteria = [["reach", [10.0, 20.0]], ["saturate", 5]]
    payload = _extract.extract_ga_parameters(ga)
    assert payload["mutation_num_genes"] == 1
    assert "mutation_percent_genes" not in payload
    assert payload["stop_criteria"] == ["reach_10.0_20.0", "saturate_5"]
    ga.mutation_probability = 0.2
    payload = _extract.extract_ga_parameters(ga)
    assert payload["mutation_probability"] == 0.2
    assert "mutation_num_genes" not in payload


def test_imported_result_marks_mixed_gene_types():
    ga = _fake_ga(); ga.gene_type_single = False
    assert _extract.extract_result(ga)["gene_type_single"] is False
