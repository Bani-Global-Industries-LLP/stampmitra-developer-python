# Releasing

Releases are tag-driven and use **PyPI trusted publishing (OIDC)**: no long-lived PyPI token is stored anywhere.

## One-time setup (maintainers)

1. On PyPI, create the project `stampmitra` (or add a *pending publisher*) and add a **trusted publisher**: owner `Bani-Global-Industries-LLP`, repository `stampmitra-developer-python`, workflow `release.yml`, environment `pypi`.
2. In GitHub, create an environment named `pypi` (optionally with required reviewers).
3. Set the repository **variable** (Settings > Secrets and variables > Actions > Variables) `PYPI_PUBLISH` to `true`.

Until `PYPI_PUBLISH` is `true`, tag pushes still build and test but the publish job is skipped.

## Cut a release

1. Update `version` in `pyproject.toml` and `src/stampmitra/_version.py`, and `CHANGELOG.md`.
2. Commit, then `git tag v0.1.0 && git push origin v0.1.0`.
3. The workflow verifies the tag matches the version, runs lint/type/tests, builds, and publishes via OIDC.
