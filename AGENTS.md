# Role Searcher development instructions

- Think through the existing behavior, requirements, and impact before editing.
- Keep commit messages short and crisp.
- Use uv for Python dependencies and environment management.
- Use Ruff for Python linting and formatting, and pytest for Python tests.
- Use pnpm for TypeScript dependencies and scripts.
- Use FastAPI for API endpoints.
- Prefer async patterns where appropriate; avoid blocking work in async handlers.
- Test changes rigorously with meaningful unit and end-to-end tests. Report what
  was run, the results, and any checks that could not run.
- For GUI changes, use a Playwright browser to inspect the rendered app and test
  the affected user flows; do not rely on a successful build alone.
- Read secrets from a .env file. Never commit secrets or include them in logs,
  screenshots, fixtures, or browser bundles. Keep .env files ignored by Git;
  example files may contain placeholders only.
- Keep these instructions in one place. Use a CLAUDE.md symlink to this file
  when helpful rather than duplicating instructions.
