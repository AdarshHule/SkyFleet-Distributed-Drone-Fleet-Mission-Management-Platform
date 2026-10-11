FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app
ARG PACKAGE

# 1) Dependencies only: cached until the lockfile or a pyproject changes
COPY uv.lock pyproject.toml ./
COPY contracts/pyproject.toml contracts/
COPY services/edge/pyproject.toml services/edge/
COPY services/telemetry/pyproject.toml services/telemetry/
COPY services/command/pyproject.toml services/command/
COPY services/gateway/pyproject.toml services/gateway/
RUN uv sync --frozen --no-dev --package ${PACKAGE} --no-install-workspace

# 2) Source code: changes often, so it comes last
COPY contracts contracts
COPY services services
RUN uv sync --frozen --no-dev --package ${PACKAGE}

# Never run as root
RUN useradd --create-home app
USER app
ENV PATH="/app/.venv/bin:$PATH"