# Releasing

Releases are automated. Pushing a version tag builds the package, publishes it to
PyPI, and attaches the built files to a GitHub Release. Nothing is uploaded by
hand.

## Steps

1. Bump the version in `vilvik/_version.py`. This is the only place the version
   lives.
2. Add a section for the new version at the top of `CHANGELOG.md`.
3. Run the tests:
   ```bash
   pip install -e ".[dev]"
   pytest
   ```
4. Commit and push:
   ```bash
   git add vilvik/_version.py CHANGELOG.md
   git commit -m "Release 0.2.3"
   git push
   ```
5. Wait for the `tests` workflow to pass on that commit.
6. Tag the release and push the tag:
   ```bash
   git tag v0.2.3
   git push origin v0.2.3
   ```

The `release` workflow does the rest: it builds the wheel and sdist, publishes
them to PyPI, and creates a GitHub Release with both files attached. Follow it
with `gh run watch` or the Actions tab.

## Rules

- The tag must match `vilvik/_version.py` and carries a leading `v`, for example
  `v0.2.3`. The tag is what triggers the release.
- Every release needs a new version number. PyPI does not allow re-uploading or
  overwriting a version that already exists.
- Do not run `twine upload` or upload files to the GitHub Release by hand. The
  tag does both for you.

## Manual fallback

`publish.sh` can build and upload to PyPI from your machine if you ever need it.
It does not run the tests, so run `pytest` first.

## One-time setup (maintainers)

Done once per project. No API token is involved, because PyPI trusted publishing
is tokenless.

- On the PyPI `vilvik` project, open Settings, then Publishing, and add a GitHub
  publisher: owner `VilvikInc`, repository `vilvik-python`, workflow
  `release.yml`, environment `pypi`.
- In the GitHub repo, open Settings, then Environments, and create an environment
  named `pypi`.
