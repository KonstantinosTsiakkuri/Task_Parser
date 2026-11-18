import asyncio
import logging
import signal

from config import settings
from db.session import engine
from logging_config import setup_logging
from scheduler.jobs import create_scheduler

logger = logging.getLogger(__name__)


async def main() -> None:
    """Долгоживущий воркер: синхронизирует задачи Codeforces каждые SYNC_IN_MIN минут."""
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Windows: обработчики сигналов в asyncio не поддерживаются, Ctrl+C придёт как KeyboardInterrupt
            pass

    scheduler = create_scheduler(settings.SYNC_IN_MIN)
    scheduler.start()
    logger.info("Воркер запущен, интервал синхронизации %d мин", settings.SYNC_IN_MIN)
    try:
        await stop_event.wait()
    finally:
        scheduler.shutdown(wait=False)
        await engine.dispose()
        logger.info("Воркер остановлен")


if __name__ == "__main__":
    setup_logging()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
