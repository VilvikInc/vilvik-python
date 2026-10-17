# SDK and PyGAD compatibility

`test_pygad_compatibility.py` runs real GA instances and exercises public
`vilvik.push()` and `GA.push_to_vilvik()`. It intercepts HTTP with `responses`,
but uses the actual source capture, extraction, JSON encoding, models and GA
execution. No production or beta credentials are used.

Coverage includes default/integer/NumPy/precision/mixed gene types, populations
and best results, scalar/multiple objectives, parsed stop criteria, default
and adaptive mutation controls, all seven lifecycle callbacks, NumPy gene
spaces, `range` gene spaces, SBX/polynomial/NSGA-III tuning, PyGAD 3.9
categorical genes, population opt-out, dry runs and explicit fitness source overrides.
Batch fitness size, mutation by replacement, saved solutions and thread
parallelism are checked for both export fidelity and executable continuation.
Exported constructor parameters and code reconstruct a GA that runs another
generation; this detects incompatible normalized PyGAD attributes rather than
only asserting that a fake object produces a particular JSON dictionary.

```sh
python -m pip install -e '.[dev,compatibility]'
python -m pytest -q
```

The dedicated GitHub workflow tests the current SDK with PyGAD 3.6.0, latest
PyPI PyGAD, and PyGAD's `master` branch on Python 3.9/3.12. It runs on pushes,
pull requests, daily, and manually. All SDK tests run in each job.
The ordinary SDK workflow also installs the compatibility extra, so the real
PyGAD tests run on every supported Python version, 3.9 through 3.12. These
compatibility jobs should pass before an SDK release. PyGAD has the reciprocal
workflow against released and development SDK versions. The daily run detects
a new PyGAD release or a change on PyGAD's `master` within a day, even without
commits in this repository.

## New PyGAD parameters

`test_pygad_parameter_coverage.py` reads the parameters of `pygad.GA.__init__`
and fails when one is not exported (`GA_PARAM_ATTRS` in `vilvik/_extract.py`),
captured as code, or listed in that file with a reason. Against PyGAD's
`master` this flags a new parameter before PyGAD releases it. On PyGAD 3.9 and
newer it also fails when a parameter the SDK knows is removed or renamed. It
also checks that varied gene spaces (`range`, NumPy arrays, tuples, NumPy
scalars, `None` entries) export as strict JSON and rebuild a runnable GA.

When a scheduled or manual run fails, the workflow opens an issue labelled
`pygad-compatibility`, or comments on the open one, with the unhandled
parameters for latest and development PyGAD and a link to the run. Close the
issue once the SDK handles them. PyGAD releases are never blocked by this.
Run `python tests/test_pygad_parameter_coverage.py` to print the same report
locally.

PyGAD 3.6.0 predates the `GA.push_to_vilvik()` wrapper. Only that wrapper case
is explicitly skipped for 3.6.0; `vilvik.push()` and the other compatibility
cases still run. A missing wrapper on current PyGAD fails the test. The release
workflow runs the full SDK suite with released PyGAD before building/publishing.

Without the extra, these tests skip in lightweight SDK-only environments.
Dedicated CI explicitly verifies dependency imports first. This suite does
not emulate the cloud server, sandbox or billing: use the Vilvik server's
opt-in live campaign for deployment validation as well.
