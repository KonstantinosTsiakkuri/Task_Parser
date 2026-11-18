import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from clients.codeforces import CodeforcesClient
from db.session import async_session
from repositories.tasks import TaskRepository
from services.tag_names import TAG_NAMES_RU

logger = logging.getLogger(__name__)


class SyncService:
    """Забирает задачи с Codeforces и записывает их в БД."""

    def __init__(
        self,
        client: CodeforcesClient | None = None,
        session_factory: async_sessionmaker[AsyncSession] = async_session,
    ) -> None:
        self.client = client or CodeforcesClient()
        self.session_factory = session_factory

    async def sync(self) -> int:
        """Полная синхронизация в одной транзакции. Возвращает число обработанных задач."""
        tasks = await self.client.fetch_tasks()
        logger.info("Получено задач с Codeforces: %d", len(tasks))

        # ON CONFLICT не допускает две одинаковые строки в одном INSERT — убираем дубли заранее.
        unique = {(task.cf_contest_id, task.index): task for task in tasks}
        tasks = list(unique.values())

        tag_names = sorted({tag for task in tasks for tag in task.tags})

        async with self.session_factory() as session:
            repo = TaskRepository(session)
            await repo.upsert_tasks(tasks)
            await repo.upsert_tags(tag_names, TAG_NAMES_RU)
            await repo.link_tags(tasks)
            await session.commit()

        logger.info("Синхронизация завершена: задач %d, тегов %d", len(tasks), len(tag_names))
        return len(tasks)
