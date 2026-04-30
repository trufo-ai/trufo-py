# Contributing

During the alpha release phase, external contributors may raise issues, but may not make PRs.

Please refer to the `lib-dev` skill in `skills/` for guidance on coding.

## Release Process

Publishing uses **Trusted Publishing** (OIDC) via GitHub Actions — no API tokens needed.

### Steps

1. **Prepare a release PR on `main`** (or work directly on `main` for small releases):

   a. Update `version` in `pyproject.toml` (e.g. `0.1.1` → `0.1.2`).

   b. Update `CHANGELOG.md`:
      - Rename `## [Unreleased]` to `## [X.Y.Z] — YYYY-MM-DD`.
      - Add a new empty `## [Unreleased]` section at the top.
      - Update the comparison links at the bottom of the file.

   c. Commit with message: `Release vX.Y.Z`.

2. **Merge to `main`** via PR (or push directly if the change is only the version bump + changelog).

3. **Create a GitHub Release**:
   - Tag: `vX.Y.Z` (e.g. `v0.1.2`), pointed at the release commit on `main`.
   - Title: `vX.Y.Z`.
   - Body: paste the changelog section for this version.

4. **CI publishes automatically** — the `publish.yml` workflow triggers on release creation,
   builds the package, and uploads to PyPI via OIDC.

5. **Verify** the release appears on [PyPI](https://pypi.org/project/trufo/) and `pip install trufo==X.Y.Z` works.

### Configuration (one-time)

- **PyPI**: A trusted publisher is registered for `trufo-ai/trufo-py` → `publish.yml` → `pypi` environment.
- **GitHub**: A `pypi` environment is configured in the repo settings (Settings → Environments).
