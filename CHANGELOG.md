# Changelog

All notable changes to the `vilvik` Python SDK are recorded here. The format
follows [Keep a Changelog](https://keepachangelog.com/), and the project uses
[semantic versioning](https://semver.org/).

## [0.4.0]

### Fixed

- `submissions.create` now sends an entry symbol for every code field. The
  runtime requires the top-level name to call and no longer guesses, so a
  submission that omitted it was accepted and then failed during execution
  with "Entry symbol is required". The entry is auto-detected from the
  source (the last top-level def or class), and an explicit `<role>_entry`
  still overrides the detection.
- `code_uploads.create` now matches the REST API: it takes `content=` and
  sends `{"content": ...}` (previously `field=`/`code=`, which the server
  rejected). `CodeUpload` now exposes `code_id`, `content`, `content_size`,
  `content_sha256`, `created_at`, `expires_at`, and `is_expired`. Reference
  an upload from a submission with `<role>_id=upload.code_id` (for example
  `fitness_func_id=upload.code_id`).

### Known limitations

- `code_uploads.list()` calls an endpoint the REST API does not expose yet;
  use `code_uploads.get(code_id)` to fetch a single upload.

## [0.3.0]

### Added

- `client.results.delete(result_id)` wraps `DELETE /api/v1/results/{id}`.
- `client.results.update(result_id, name=..., is_shared=...)` wraps
  `PATCH /api/v1/results/{id}`; only the fields you pass are sent.
- `Result` now exposes `name` and `is_shared`.

## [0.2.2]

### Changed

- The package summary now describes Vilvik as an optimization platform rather
  than naming a single method.
- The README links to the SDK guide and the REST API reference.

### Fixed

- The `User-Agent` header now tracks the package version instead of staying
  pinned to an older string. The version is defined in one place so it cannot
  drift again.

## [0.2.1]

Packaging and project-metadata release. No changes to the public API.

### Changed

- The SDK now lives in its own repository and the distribution bundles a license
  file. Project URLs point at the new repository.

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

[0.2.2]: https://github.com/VilvikInc/vilvik-python/releases/tag/v0.2.2
[0.2.1]: https://github.com/VilvikInc/vilvik-python/releases/tag/v0.2.1
[0.2.0]: https://github.com/VilvikInc/vilvik-python/releases/tag/v0.2.0
