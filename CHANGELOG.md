# Changelog

All notable changes to the `vilvik` Python SDK are recorded here. The format
follows [Keep a Changelog](https://keepachangelog.com/), and the project uses
[semantic versioning](https://semver.org/).

## [0.2.1]

Packaging and project-metadata release. No changes to the public API.

### Changed

- The SDK now lives in its own repository and the distribution bundles a license
  file. Project URLs point at the new repository.
- The package summary now describes Vilvik as an optimization platform rather
  than naming a single method.

## [0.2.0]

First public release.

### Added

- `Client` with namespaced resources: `submissions`, `results`, `code_uploads`,
  `webhooks`, and `imports`. The API key is read from the `api_key` argument,
  then the `VILVIK_API_KEY` environment variable, then the credential cached by
  `vilvik login`.
- `vilvik.run(...)`, a context manager that submits a run, blocks until it
  finishes, and cancels it if you leave the block early.
- `vilvik.push(ga, ...)` for sending a local `pygad.GA` instance to Vilvik as an
  editable, continuable record. Source for the fitness function and callbacks is
  captured automatically, with explicit overrides for the cases auto-capture
  cannot resolve.
- `vilvik.login()`, a device-authorization flow that opens the browser, waits
  for approval, and caches the resulting key. Also available as the `vilvik
  login` command.
- `Results.wait_for(...)` to poll a submission to a terminal state, and
  `Results.continue_run(...)` to branch a new run from a finished result.
- Typed dataclasses for every response (`Submission`, `Result`, `CodeUpload`,
  `Webhook`, `ImportRecord`, `Page`) that keep unmodelled fields on `raw` for
  forward compatibility.
- An exception hierarchy rooted at `VilvikError` (`AuthenticationError`,
  `NotFoundError`, `ValidationError`, `RateLimitError`, `APIError`,
  `TimeoutError`, `CaptureError`).

[0.2.1]: https://github.com/VilvikInc/vilvik-python/releases/tag/v0.2.1
[0.2.0]: https://github.com/VilvikInc/vilvik-python/releases/tag/v0.2.0
