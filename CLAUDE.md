# SkyFleet: instructions for Claude Code

## Project
Distributed drone fleet and mission platform (learning project). Python 3.12 + uv, FastAPI,
Pydantic v2, pytest, ruff. Services in services/<name>/, shared event schemas in contracts/.
Import workspace packages by name (`skyfleet_edge`, `skyfleet_contracts`), never via `src.`.

## Commands
- `uv sync`: install dependencies for the whole workspace
- `uv run pytest contracts -v`: contract tests
- `uv run pytest services/edge -v`: edge service tests
- `uv run pytest services/edge/tests/test_drone.py::test_idle_drone_does_not_move -v`: run a single test
- `uv run ruff check .`: lint (add `--fix` for safe auto-fixes)

## How to work with me
- I am learning. Before editing any file, state your plan in 3-5 lines and wait for my approval.
- Keep changes small: one feature or fix per change.
- Briefly explain non-obvious design choices.
- Never invent event fields. Read contracts/ first; if something is missing, ask.
- Do not create or edit anything in docs/. I write the design docs myself.
- Never write secrets, keys or credentials into files.
- If requirements are ambiguous, ask instead of guessing.