# SDK and PyGAD compatibility

`test_pygad_compatibility.py` runs real GA instances and exercises public
`vilvik.push()` and `GA.push_to_vilvik()`. It intercepts HTTP with `responses`,
but uses the actual source capture, extraction, JSON encoding, models and GA
execution. No production or beta credentials are used.

Coverage includes default/integer/NumPy/precision/mixed gene types, populations
and best results, scalar/multiple objectives, parsed stop criteria, default
and adaptive mutation controls, all seven lifecycle callbacks, NumPy gene
spaces, population opt-out, dry runs and explicit fitness source overrides.
Exported constructor parameters and code reconstruct a GA that runs another
generation; this detects incompatible normalized PyGAD attributes rather than
only asserting that a fake object produces a particular JSON dictionary.

```sh
python -m pip install -e '.[dev,compatibility]'
python -m pytest -q
```

The dedicated GitHub workflow tests the current SDK with PyGAD 3.6.0, latest
PyPI PyGAD, and PyGAD's `master` branch on Python 3.9/3.12. It runs on pushes,
pull requests, every Monday, and manually. All SDK tests run in each job.
The ordinary SDK workflow also installs the compatibility extra, so the real
PyGAD tests run on every supported Python version, 3.9 through 3.12. These
compatibility jobs should pass before an SDK release. PyGAD has the reciprocal
workflow against released and development SDK versions. Weekly jobs detect
upstream releases even without commits in this repository.

PyGAD 3.6.0 predates the `GA.push_to_vilvik()` wrapper. Only that wrapper case
is explicitly skipped for 3.6.0; `vilvik.push()` and the other compatibility
cases still run. A missing wrapper on current PyGAD fails the test. The release
workflow runs the full SDK suite with released PyGAD before building/publishing.

Without the extra, these tests skip in lightweight SDK-only environments.
Dedicated CI explicitly verifies dependency imports first. This suite does
not emulate the cloud server, sandbox or billing: use the Vilvik server's
opt-in live campaign for deployment validation as well.
