import logging
from datetime import datetime, timezone

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.exc import SQLAlchemyError

from clients.codeforces import CodeforcesAPIError
from services.sync import SyncService

logger = logging.getLogger(__name__)

SYNC_JOB_ID = "sync_tasks"


async def sync_tasks_job() -> None:
    """Одна синхронизация. Ошибки логируются и не роняют воркер — следующая попытка будет по расписанию."""
    try:
        count = await SyncService().sync()
    except (httpx.HTTPError, CodeforcesAPIError) as exc:
        logger.error("Codeforces недоступен, синхронизация пропущена: %r", exc)
    except SQLAlchemyError:
        logger.exception("Ошибка БД при синхронизации")
    except Exception:
        logger.exception("Непредвиденная ошибка синхронизации")
    else:
        logger.info("Синхронизировано задач: %d", count)


def create_scheduler(interval_minutes: int) -> AsyncIOScheduler:
    """Планировщик с задачей синхронизации: сразу при старте и далее каждые interval_minutes минут."""
    scheduler = AsyncIOScheduler(timezone=timezone.utc)
    scheduler.add_job(
        sync_tasks_job,
        trigger="interval",
        minutes=interval_minutes,
        id=SYNC_JOB_ID,
        next_run_time=datetime.now(timezone.utc),  # первый запуск — немедленно
        max_instances=1,  # не запускать новую синхронизацию, пока идёт предыдущая
        coalesce=True,  # пропущенные запуски схлопываются в один
        misfire_grace_time=60,
    )
    return scheduler
