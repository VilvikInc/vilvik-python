"""Extract GA parameters + run outcome from a duck-typed pygad.GA.

Never imports pygad or numpy. numpy arrays/scalars are coerced to JSON
types via their .tolist()/.item() methods or python casts.
"""
from __future__ import annotations

from typing import Any, Dict

GA_PARAM_ATTRS = (
    "num_generations", "sol_per_pop", "num_parents_mating", "num_genes",
    "gene_type", "gene_space", "init_range_low", "init_range_high",
    "parent_selection_type", "K_tournament", "crossover_type",
    "crossover_probability", "mutation_type", "mutation_percent_genes",
    "mutation_num_genes", "mutation_probability", "random_mutation_min_val",
    "random_mutation_max_val", "keep_parents", "keep_elitism",
    "allow_duplicate_genes", "random_seed", "stop_criteria",
)


def _jsonable(value: Any) -> Any:
    """Coerce numpy / exotic scalars + arrays to JSON-native types."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "tolist"):
        return value.tolist()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


def extract_ga_parameters(ga: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for attr in GA_PARAM_ATTRS:
        if not hasattr(ga, attr):
            continue
        val = getattr(ga, attr)
        if val is None:
            continue
        if isinstance(val, type):
            out[attr] = getattr(val, "__name__", str(val))
            continue
        if callable(val) and not isinstance(val, (list, tuple, dict)):
            # A custom operator callable can't transfer as a string knob; skip it.
            continue
        out[attr] = _jsonable(val)
    return out


def extract_result(ga: Any, *, include_population: bool = True) -> Dict[str, Any]:
    best_solution, best_fitness, best_idx = ga.best_solution()
    out: Dict[str, Any] = {
        "best_solution": _jsonable(best_solution),
        "best_solution_idx": int(best_idx),
        "best_solution_fitness": _jsonable(best_fitness),
        "best_solutions_fitness": _jsonable(getattr(ga, "best_solutions_fitness", []) or []),
        "generations_completed": int(getattr(ga, "generations_completed", 0) or 0),
        "best_solution_generation": int(getattr(ga, "best_solution_generation", 0) or 0),
    }
    lgf = getattr(ga, "last_generation_fitness", None)
    if lgf is not None:
        out["last_generation_fitness"] = _jsonable(lgf)
    if include_population:
        pop = getattr(ga, "population", None)
        if pop is not None:
            out["population"] = _jsonable(pop)
    return out
