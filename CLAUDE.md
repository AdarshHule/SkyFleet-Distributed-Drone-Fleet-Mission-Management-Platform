# SkyFleet: instructions for Claude Code

## Project
Distributed drone fleet and mission platform (learning project). Python 3.12 + uv, FastAPI,
Pydantic v2, pytest, ruff. Services in services/<name>/, shared event schemas in contracts/.

## How to work with me
- I am learning. Before editing any file, state your plan in 3-5 lines and wait for my approval.
- Keep changes small: one feature or fix per change.
- Briefly explain non-obvious design choices.
- Never invent event fields. Read contracts/ first; if something is missing, ask.
- Do not create or edit anything in docs/. I write the design docs myself.
- Never write secrets, keys or credentials into files.
- If requirements are ambiguous, ask instead of guessing.