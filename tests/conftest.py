"""Общие фикстуры. Тесты работают с отдельной БД (по умолчанию task_parser_test), рабочую БД не трогают."""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

# Подменяем имя БД ДО импорта config: settings = Settings() читается один раз при первом импорте,
# а переменная окружения важнее значения из .env.
TEST_DB_NAME = os.environ.get("TEST_DB_NAME", "task_parser_test")
if not TEST_DB_NAME.endswith("_test"):
    raise RuntimeError(f"Тестовая БД должна оканчиваться на _test, получено: {TEST_DB_NAME}")
os.environ["DB_NAME"] = TEST_DB_NAME

import asyncpg  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker  # noqa: E402

from config import settings  # noqa: E402
from db.session import async_session, engine  # noqa: E402
from schemas import TaskData  # noqa: E402
from tests.helpers import REAL_TASKS, load_tasks  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


async def recreate_test_database() -> None:
    """Пересоздаёт тестовую БД: каждый прогон тестов начинается с пустой базы и проверяет миграции с нуля."""
    conn = await asyncpg.connect(
        user=settings.DB_USER,
        password=settings.DB_PASSWORD.get_secret_value(),
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database="postgres",
    )
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
async def test_database() -> AsyncIterator[None]:
    await recreate_test_database()
    # alembic в отдельном процессе: его env.py сам вызывает asyncio.run(), что нельзя внутри работающего loop
    await asyncio.to_thread(
        subprocess.run, [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, check=True, env=os.environ
    )
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_tables() -> AsyncIterator[None]:
    yield
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE task_tags, tasks, tags, selections RESTART IDENTITY CASCADE"))


@pytest.fixture
def session_factory() -> async_sessionmaker[AsyncSession]:
    return async_session


@pytest.fixture
async def real_tasks() -> list[TaskData]:
    await load_tasks(REAL_TASKS)
    return REAL_TASKS
