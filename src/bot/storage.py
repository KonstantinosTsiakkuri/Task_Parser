import asyncio
import logging

from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

PING_TIMEOUT = 5


async def create_storage(host: str, port: int) -> BaseStorage:
    """FSM-хранилище в Redis (переживает перезапуск бота); если Redis недоступен — в памяти процесса."""
    redis = Redis(host=host, port=port, socket_connect_timeout=3)
    try:
        # общий предел: redis-py сам повторяет попытки, и на Windows отказ в соединении растягивается до ~30 с
        await asyncio.wait_for(redis.ping(), timeout=PING_TIMEOUT)
    except (RedisError, OSError, TimeoutError) as exc:
        await redis.aclose()
        logger.warning("Redis %s:%s недоступен (%r) — состояния FSM храню в памяти", host, port, exc)
        return MemoryStorage()
    logger.info("FSM-хранилище: Redis %s:%s", host, port)
    return RedisStorage(redis)
