# trufo-py Release Playbook

Playbook for publishing a new `trufo-py` release to PyPI. Publishing uses
**Trusted Publishing** (OIDC) via GitHub Actions — no API tokens needed.

---

## Steps

### 1. Prepare the release commit

On the release branch (or directly on `main` for small releases):

a. Update `version` in `pyproject.toml` (e.g. `0.3.3` → `0.4.0`).

b. Update `__version__` in `src/trufo/__init__.py` to match.

c. Update `CHANGELOG.md`:
   - Rename `## [Unreleased]` to `## [X.Y.Z] — YYYY-MM-DD`.
   - Add a new empty `## [Unreleased]` section at the top.
   - Update the comparison links at the bottom of the file.

d. Update `README.md` if the "Optional Provenance Engine" section contains
   version-specific prose (e.g. pin ranges, platform notes) that changed.

e. Update `CLAUDE.md` if any key facts changed (signing mode availability,
   docs map, dependency requirements).

f. Update the `trufo-provenance` pin in `pyproject.toml` extras if the minimum
   required `trufo-provenance` version changed (e.g. `>=0.1.2,<0.2` → `>=0.2.0,<0.3`).

g. Commit with message: `chore: prepare trufo X.Y.Z release`.

### 2. Merge to `main`

Merge via PR (or push directly if the change is only the version bump + changelog).

### 3. Create a GitHub Release

- Tag: `vX.Y.Z` (e.g. `v0.4.0`), pointed at the release commit on `main`.
- Title: `vX.Y.Z`.
- Body: paste the changelog section for this version.

### 4. CI publishes automatically

The `publish.yml` workflow triggers on release creation, builds the package, and
uploads to PyPI via OIDC. The run appears in GitHub Actions as
`release: trufo-py vX.Y.Z`.

### 5. Verify

Check the release on [PyPI](https://pypi.org/project/trufo/) and confirm
`pip install trufo==X.Y.Z` works.

---

## Configuration (one-time)

- **PyPI**: A trusted publisher is registered for `trufo-ai/trufo-py` →
  `publish.yml` → `pypi` environment.
- **GitHub**: A `pypi` environment is configured in the repo settings
  (Settings → Environments).
