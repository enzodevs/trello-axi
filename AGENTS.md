# Project instructions

- Python 3.13+; manage environments and dependencies with uv.
- Format and lint with Ruff; type-check with ty; test with pytest.
- Run: `uv sync --locked --all-groups && uv run ruff format --check . && uv run ruff check . && uv run ty check . && uv run pytest`.
- Keep domain logic independent from I/O and test user-visible behavior.
