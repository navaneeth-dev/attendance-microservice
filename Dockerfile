# First, build the application in the `/app` directory.
# See `Dockerfile` for details.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install tesseract-ocr -y

COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH"

RUN ["playwright", "install", "--with-deps", "firefox"]

CMD ["fastapi", "run", "--host", "0.0.0.0", "--port", "8080", "/app/app/main.py"]
