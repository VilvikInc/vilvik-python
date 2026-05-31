# vilvik

Official Python SDK for [Vilvik](https://vilvik.com), a cloud platform for
running and tracking optimization jobs through a REST API, with scoped keys
and webhook delivery. Vilvik currently runs Genetic Algorithm (PyGAD)
workloads, and this SDK gives your Python code a typed client, a
submit-and-wait helper, and a clean error hierarchy to drive them.

**Documentation:** [SDK guide](https://vilvik.com/docs/sdk/) ·
[REST API reference](https://vilvik.com/docs/api/) ·
[all docs](https://vilvik.com/docs/)

```bash
pip install vilvik
```

## Quick start

```python
import vilvik

client = vilvik.Client(api_key="vlk_live_…")

submission = client.submissions.create(
    fitness_func="""
def fitness_func(ga_instance, solution, idx):
    return -sum(s * s for s in solution)
""",
    num_genes=5,
    num_generations=100,
    sol_per_pop=50,
    name="quadratic-minimisation",
)

print(submission.id, submission.status)        # "abc123…", "queued"

result = client.results.wait_for(submission.id, timeout=300)
print(result.best_fitness, result.best_solution)
```

## The `run()` one-liner

For scripts and notebook cells, `vilvik.run(...)` packages create-and-wait
into a context manager that also cancels the run if you exit the block
early:

```python
import vilvik

fn = """
def fitness_func(ga_instance, solution, idx):
    return -sum(s * s for s in solution)
"""

with vilvik.run(fitness_func=fn, num_genes=5, num_generations=50) as result:
    print(result.best_fitness)
```

The API key is read from `VILVIK_API_KEY` if you do not pass it
explicitly.

## Quick submissions

Quick submission types let you run a built-in problem without writing a
fitness function. Set `submission_type` and pass that problem's inputs.
You can leave `num_generations` and `sol_per_pop` unset, and the quick
type applies its own defaults:

```python
import vilvik

client = vilvik.Client(api_key="vlk_live_…")

# Find a subset of the integers that sums to the target.
submission = client.submissions.create(
    submission_type="quick_binary_subset_sum",
    integers=[3, 7, 1, 9, 4, 2, 8, 5],
    target=20,
)

# A 0/1 knapsack with explicit items and a single capacity dimension.
submission = client.submissions.create(
    submission_type="quick_knapsack",
    item_names=["map", "compass", "water", "rope"],
    item_values=[5, 8, 3, 4],
    item_weights=[[2], [1], [3], [2]],
    dimension_names=["weight"],
    dimension_capacities=[5],
)
```

When you ask the service to generate the inputs for you (for example
passing `num_integers` instead of an explicit `integers` list), the
response echoes what it picked under `submission.generated`:

```python
submission = client.submissions.create(
    submission_type="quick_binary_subset_sum",
    num_integers=8,
    target=20,
)
print(submission.generated)   # {"integers": [...]}
```

The machine learning types tune model hyperparameters with a genetic
algorithm. Over the API they run on a built-in dataset only (`dataset_name`
is `iris`, `breast_cancer`, or `random`); training on your own uploaded
data is available on the website but not yet over the API or SDK:

```python
submission = client.submissions.create(
    submission_type="quick_sklearn_rfc_hyperparameters",
    dataset_name="iris",
    hyperparameters={
        "n_estimators": {"tune": True, "min": 50, "max": 150},
        "max_depth": {"fixed": 10},
    },
)
```

## Listing and pagination

The list endpoints return a `Page` whose items are typed dataclasses; for
walking everything use `iter_all`:

```python
page = client.submissions.list(limit=25)
for sub in page:
    print(sub.id, sub.status, sub.name)

# All submissions, transparently following the cursor:
for sub in client.submissions.iter_all():
    ...
```

## Branching a finished run

`Results.continue_run` branches a fresh run from a finished result. Each
call creates a child submission whose `parent_submission` is the result
you forked from. Pass any GA parameter you want to override:

```python
parent = client.results.get(result_id)
variant_a = client.results.continue_run(parent.id, mutation_probability=0.10)
variant_b = client.results.continue_run(parent.id, sol_per_pop=100)
```

The Vilvik dashboard renders the resulting lineage as an interactive tree
on the result page.

## Errors

Every SDK error inherits from `vilvik.VilvikError`. Subclasses let you
catch specific failure modes:

```python
try:
    client.submissions.get("does-not-exist")
except vilvik.NotFoundError as e:
    print("Not found:", e.request_id)
except vilvik.RateLimitError as e:
    print("Slow down, retry after", e.retry_after, "seconds")
except vilvik.AuthenticationError:
    print("Check your API key and scopes")
except vilvik.VilvikError:
    print("Something else went wrong")
```

## Configuration

| Argument        | Default                            | Notes                                              |
| --------------- | ---------------------------------- | -------------------------------------------------- |
| `api_key`       | `os.environ["VILVIK_API_KEY"]`     | Required. Bearer token created in the dashboard.   |
| `base_url`      | `https://vilvik.com/api/v1`        | Override for staging or self-hosted instances.     |
| `timeout`       | `60.0` seconds                     | Per-HTTP-request timeout.                          |
| `max_retries`   | `2`                                | Idempotent (GET / HEAD) retries on network errors. |

## Documentation

The full SDK guide lives at <https://vilvik.com/docs/sdk/>, with a page per
feature:

- [Installation and configuration](https://vilvik.com/docs/sdk/installation/)
- [Submissions](https://vilvik.com/docs/sdk/submissions/),
  [results](https://vilvik.com/docs/sdk/results/), and the
  [`run()` helper](https://vilvik.com/docs/sdk/run-helper/)
- [Importing a local PyGAD run](https://vilvik.com/docs/sdk/imports/),
  [code uploads](https://vilvik.com/docs/sdk/code-uploads/), and
  [webhooks](https://vilvik.com/docs/sdk/webhooks/)
- [Error handling](https://vilvik.com/docs/sdk/errors/) and
  [worked examples](https://vilvik.com/docs/sdk/examples/)

Every SDK page links to the matching
[REST API reference](https://vilvik.com/docs/api/), so you can drop down to the
raw HTTP calls whenever you need to.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT.
