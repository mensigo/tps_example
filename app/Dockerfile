FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.6.0 /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app.py ./

EXPOSE 8088
CMD [".venv/bin/uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8088"]
