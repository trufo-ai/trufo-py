# Contributing

During the alpha release phase, external contributors may raise issues, but may not make PRs.

## Internal Development

Please refer to the `lib-dev` skill in `skills/` for guidance on coding.

### Publishing to PyPI

Publishing uses **Trusted Publishing** (OIDC) via GitHub Actions — no API tokens needed.

1. Update `version` in `pyproject.toml`.
2. Merge to `main`.
3. Create a **GitHub Release** with a tag matching the version (e.g. `v0.1.0`).
4. The `publish.yml` workflow builds and uploads to PyPI automatically.

Configuration:
- **PyPI**: A trusted publisher is registered for `trufo-ai/trufo-py` → `publish.yml` → `pypi` environment.
- **GitHub**: A `pypi` environment is configured in the repo settings (Settings → Environments).
