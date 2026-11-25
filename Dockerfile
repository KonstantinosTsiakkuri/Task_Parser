# Один образ для всех сервисов приложения: bot, worker и migrate отличаются только командой (command в compose).

# ---------- стадия 1: установка зависимостей ----------
FROM python:3.13-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true

RUN pip install "poetry==2.4.3"

WORKDIR /app
# сначала только файлы зависимостей: пока они не менялись, Docker берёт этот слой из кэша
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

# ---------- стадия 2: итоговый образ ----------
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN useradd --create-home --uid 1000 app

COPY --from=builder /app/.venv /app/.venv
COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src

USER app

CMD ["python", "src/main_bot.py"]
