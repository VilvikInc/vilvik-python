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
    if isinstance(value, type):
        return ("numpy." if value.__module__.startswith("numpy") else "") + value.__name__
    if hasattr(value, "tolist"):
        return _jsonable(value.tolist())
    if hasattr(value, "item"):
        try:
            return _jsonable(value.item())
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
        if attr == "gene_type":
            # PyGAD normalizes even the default float into [float, None].
            # Preserve precision and per-gene types using the server's
            # explicit custom_gene_type expression rather than JSON types.
            single = getattr(ga, "gene_type_single", isinstance(val, type))
            if single and isinstance(val, (list, tuple)) and len(val) == 2 and val[1] is None:
                val = val[0]
            if isinstance(val, type):
                out[attr] = _jsonable(val)
            else:
                def expression(value):
                    if isinstance(value, type):
                        return _jsonable(value)
                    if (isinstance(value, (list, tuple)) and len(value) == 2
                            and isinstance(value[0], type) and value[1] is None):
                        return expression(value[0])
                    if isinstance(value, (list, tuple)):
                        return "[" + ", ".join(expression(v) for v in value) + "]"
                    return repr(_jsonable(value))
                out[attr] = "custom"
                out["custom_gene_type"] = expression(val)
            continue
        if isinstance(val, type):
            out[attr] = getattr(val, "__name__", str(val))
            continue
        if callable(val) and not isinstance(val, (list, tuple, dict)):
            # A custom operator callable can't transfer as a string knob; skip it.
            continue
        out[attr] = _jsonable(val)
    # PyGAD retains the requested percentage alongside its derived count.
    # The server accepts one mutation control; keep the effective control.
    if out.get("mutation_probability") is not None:
        out.pop("mutation_percent_genes", None)
        out.pop("mutation_num_genes", None)
    elif out.get("mutation_num_genes") is not None:
        out.pop("mutation_percent_genes", None)
    stops = out.get("stop_criteria")
    if isinstance(stops, list):
        normalized = []
        for stop in stops:
            if isinstance(stop, (list, tuple)) and len(stop) >= 2:
                values = stop[1] if len(stop) == 2 and isinstance(stop[1], (list, tuple)) else stop[1:]
                normalized.append("_".join([stop[0]] + [str(v) for v in values]))
            else:
                normalized.append(stop)
        out["stop_criteria"] = normalized
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
        "gene_type_single": bool(getattr(ga, "gene_type_single", True)),
    }
    lgf = getattr(ga, "last_generation_fitness", None)
    if lgf is not None:
        out["last_generation_fitness"] = _jsonable(lgf)
    if include_population:
        pop = getattr(ga, "population", None)
        if pop is not None:
            out["population"] = _jsonable(pop)
    return out
