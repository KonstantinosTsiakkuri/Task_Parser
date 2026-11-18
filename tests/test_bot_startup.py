from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from redis.exceptions import ConnectionError as RedisConnectionError

import main_bot
from bot import storage


def fake_redis(ping: AsyncMock) -> MagicMock:
    redis = MagicMock()
    redis.ping = ping
    redis.aclose = AsyncMock()
    return redis


async def test_storage_uses_redis_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = fake_redis(AsyncMock(return_value=True))
    monkeypatch.setattr(storage, "Redis", MagicMock(return_value=redis))

    result = await storage.create_storage("redis", 6379)

    assert isinstance(result, RedisStorage)


async def test_storage_falls_back_to_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = fake_redis(AsyncMock(side_effect=RedisConnectionError("refused")))
    monkeypatch.setattr(storage, "Redis", MagicMock(return_value=redis))

    result = await storage.create_storage("localhost", 6379)

    assert isinstance(result, MemoryStorage)
    redis.aclose.assert_awaited_once()


async def test_main_bot_wires_dispatcher(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = MagicMock()
    bot.get_me = AsyncMock(return_value=MagicMock(username="Task_Parser2026_bot"))
    bot.set_my_commands = AsyncMock()
    bot.session.close = AsyncMock()
    monkeypatch.setattr(main_bot, "Bot", MagicMock(return_value=bot))
    monkeypatch.setattr(main_bot, "create_storage", AsyncMock(return_value=MemoryStorage()))
    started: list[Dispatcher] = []

    async def fake_start_polling(self: Dispatcher, *bots: object, **kwargs: object) -> None:
        started.append(self)

    monkeypatch.setattr(Dispatcher, "start_polling", fake_start_polling)

    await main_bot.main()

    bot.set_my_commands.assert_awaited_once_with(main_bot.COMMANDS)
    [dispatcher] = started
    assert [router.name for router in dispatcher.sub_routers] == ["common", "selection", "search", "fallback"]
    assert "selection_service" in dispatcher.workflow_data
    bot.session.close.assert_awaited_once()
