# Contributing

Thanks for your interest in improving ib-mcp!

## Quick Start
1. Fork the repository and create a branch: `git checkout -b feat/short-description`
2. Install tools:
   ```bash
   pip install poetry
   poetry install
   pre-commit install
   ```
3. Run checks locally before pushing:
   ```bash
   poetry run ruff check .
   poetry run mypy ib_mcp
   poetry run pytest -q
   ```
4. Open a Pull Request with a clear title & description (what / why). The CI must pass.

## Project Philosophy
- Read‑only access to Interactive Brokers data (no trading / order placement).
- Minimal, typed API surface; tools should return concise, LLM-friendly text.
- Keep external dependencies lean.

## Commit & PR Guidelines
- Conventional-ish concise titles (e.g. `feat: add contract details tool`, `fix: handle empty news providers`).
- Squash commits if they are noisy / WIP before requesting review.
- Address review comments via additional commits (squash optional at the end).

## Coding Standards
- Python >= 3.12
- Formatting: Ruff (imports + style) — no separate Black needed.
- Type hints required for new public functions.
- Prefer `list[...]` / `dict[...]` builtins over `typing.List` / `typing.Dict`.
- Catch broad exceptions only at integration boundaries; re-raise with context.

## Tests
Currently tests are light (no live IB calls). For new functionality:
- Add unit tests for pure helpers.
- Guard network-dependent logic behind mocks or mark as integration (skipped by default).

## Adding a New Tool
1. Add an async function inside `_register_handlers` using `@self.server.tool`.
2. Use `Annotated[...]` with short parameter docs.
3. Return a plain string; prefer human-readable tables / bullet lists.
4. Update README if it’s a user-visible capability.

## Release Workflow (Maintainers)
1. Update version in `pyproject.toml` (follow semver).
2. Update CHANGELOG (if present) / brief notes in the release form.
3. Tag & publish:
   ```bash
   git commit -am "chore(release): vX.Y.Z"
   git tag vX.Y.Z
   git push origin main --tags
   poetry build
   poetry publish  # requires configured token
   ```
4. Verify PyPI install & badge updates.

## Security / Stability
- No secrets should be committed. Pre-commit hook detects private keys.
- If handling potentially unsafe XML, consider adding additional sanitization.
- Report vulnerabilities privately via repository security advisories.

## Questions / Discussion
Open a GitHub Discussion or an issue if unsure about an approach.

Welcome aboard — happy hacking!
