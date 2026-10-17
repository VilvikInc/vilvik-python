"""Fail when PyGAD gains a constructor parameter the SDK has not classified.

The compatibility tests only cover parameters someone already wrote a test
for, so a new pygad.GA parameter used to pass CI while vilvik.push() silently
dropped it (gene_categorical in PyGAD 3.9.0). Every parameter of
pygad.GA.__init__ must be exported, captured as code, or listed below with a
reason. Run this file directly to print a Markdown report of the gaps.
"""
import inspect
import json
import sys

import numpy as np
import pytest

pygad = pytest.importorskip("pygad", reason="install the compatibility test extra")

from vilvik import _extract

# Sent as Python source in the payload's `code` block.
CAPTURED_AS_CODE = {
    "fitness_func", "on_start", "on_fitness", "on_parents", "on_crossover",
    "on_mutation", "on_generation", "on_stop", "gene_constraint",
}

# Deliberately not sent as a GA parameter.
NOT_EXPORTED = {
    "initial_population": "sent as result.population, which a continuation starts from",
    "suppress_warnings": "only controls local console warnings",
    "logger": "a local logging object with no meaning on the server",
}

# PyGAD supports these but Vilvik cannot run them yet. Export them once the
# server accepts them.
NOT_SUPPORTED_BY_VILVIK = {}


PYGAD_VERSION = tuple(int(part) for part in pygad.__version__.split(".")[:2])


def constructor_parameters():
    return [name for name in inspect.signature(pygad.GA.__init__).parameters if name != "self"]


def classified():
    return (set(_extract.GA_PARAM_ATTRS) | CAPTURED_AS_CODE
            | set(NOT_EXPORTED) | set(NOT_SUPPORTED_BY_VILVIK))


def unclassified_parameters():
    known = classified()
    return [name for name in constructor_parameters() if name not in known]


def stale_parameters():
    """Classified names that this PyGAD no longer accepts."""
    current = set(constructor_parameters())
    return sorted(name for name in classified() if name not in current)


def test_every_pygad_constructor_parameter_is_classified():
    missing = unclassified_parameters()
    assert not missing, (
        f"PyGAD {pygad.__version__} has constructor parameters the SDK does not handle: "
        f"{', '.join(missing)}. Export them in vilvik/_extract.py (GA_PARAM_ATTRS) with a "
        "compatibility test, or list them in this file with a reason.")


@pytest.mark.skipif(PYGAD_VERSION < (3, 9), reason="older PyGAD releases lack parameters the SDK knows about")
def test_no_classified_parameter_was_removed_from_pygad():
    stale = stale_parameters()
    assert not stale, (
        f"PyGAD {pygad.__version__} no longer accepts: {', '.join(stale)}. "
        "Check the release notes for a rename and update the SDK.")


def fitness(ga_instance, solution, solution_idx):
    return -float(np.sum(np.abs(solution)))


GENE_SPACES = {
    "global range": range(-3, 4),
    "per-gene range with step": [range(5), range(10, 30, 5), range(3)],
    "numpy arrays": [np.array([1, 2, 3]), np.arange(0, 1, 0.25), np.array([0.5, 1.5])],
    "tuple": pytest.param((0, 1, 2, 3), marks=pytest.mark.skipif(
        PYGAD_VERSION < (3, 7), reason="PyGAD 3.6.0 rejects a tuple gene_space")),
    "numpy scalars in dicts": [{"low": np.float64(0), "high": np.int64(3)},
                               {"low": 0, "high": 2, "step": np.float32(0.5)}, [0, 1]],
    "None entries": [None, [1, 2, 3], {"low": -1, "high": 1}],
    "mixed": [range(4), np.array([5, 6]), {"low": 0, "high": 1}],
}


@pytest.mark.parametrize("gene_space", GENE_SPACES.values(), ids=list(GENE_SPACES))
def test_gene_space_shapes_export_as_strict_json(gene_space):
    ga = pygad.GA(num_generations=1, num_parents_mating=2, sol_per_pop=4, num_genes=3,
                  fitness_func=fitness, gene_space=gene_space, random_seed=3,
                  init_range_low=np.float64(-2), init_range_high=np.int32(2),
                  suppress_warnings=True)
    ga.run()
    parameters = _extract.extract_ga_parameters(ga)
    restored = json.loads(json.dumps(parameters, allow_nan=False))
    params = dict(restored, gene_type=float, fitness_func=fitness,
                  num_generations=1, suppress_warnings=True)
    params.pop("custom_gene_type", None)
    pygad.GA(**params).run()
    result = _extract.extract_result(ga)
    json.dumps(result, allow_nan=False)


def report():
    """Markdown for the issue the scheduled workflow opens on failure."""
    lines = [f"PyGAD {pygad.__version__} (Python {sys.version.split()[0]})", ""]
    missing, stale = unclassified_parameters(), stale_parameters()
    if missing:
        lines.append("New constructor parameters the SDK does not handle:")
        lines += [f"- `{name}`" for name in missing]
    if stale and PYGAD_VERSION >= (3, 9):
        lines.append("Parameters the SDK knows that this PyGAD no longer accepts:")
        lines += [f"- `{name}`" for name in stale]
    if not missing and not (stale and PYGAD_VERSION >= (3, 9)):
        lines.append("Every constructor parameter is classified. See the failing tests in the run log.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
