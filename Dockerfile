FROM python:3.13.18-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /usr/local/bin/uv

# make lets `docker compose exec web make test` work.
RUN apt-get update \
    && apt-get install -y --no-install-recommends make \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 app \
    && mkdir /app /opt/venv \
    && chown app:app /app /opt/venv

USER app
WORKDIR /app

# The virtual environment lives outside /app so the source mount does not hide it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY --chown=app:app pyproject.toml uv.lock .python-version ./
RUN uv sync --locked

COPY --chown=app:app . .

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
