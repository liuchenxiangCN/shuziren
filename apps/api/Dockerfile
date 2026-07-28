FROM ghcr.io/astral-sh/uv:0.5.11 AS uv

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev

COPY apps/api/app ./app
COPY docs/demo_data ./docs/demo_data

EXPOSE 18080

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "18080", "--no-access-log"]
