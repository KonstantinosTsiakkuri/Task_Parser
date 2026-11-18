import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.session import async_session
from repositories.selections import SelectionRepository
from repositories.tasks import TaskRepository
from schemas import TagInfo, TaskInfo

logger = logging.getLogger(__name__)

SELECTION_SIZE = 10


class UnknownTagError(Exception):
    """Тега с таким id нет в БД."""


@dataclass
class SelectionResult:
    """Итог запроса подборки. selection_id is None — свободных задач нет, подборка не создана."""

    rating: int
    tag: TagInfo
    selection_id: int | None = None
    tasks: list[TaskInfo] = field(default_factory=list)
    requested: int = SELECTION_SIZE

    @property
    def is_empty(self) -> bool:
        return not self.tasks

    @property
    def is_complete(self) -> bool:
        return len(self.tasks) == self.requested


class SelectionService:
    """Подборки задач: каждая задача попадает максимум в одну подборку (tasks.selection_id)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] = async_session) -> None:
        self.session_factory = session_factory

    async def get_ratings(self) -> list[int]:
        """Сложности, для которых ещё можно собрать подборку."""
        async with self.session_factory() as session:
            return await TaskRepository(session).get_free_ratings()

    async def get_tags(self, rating: int) -> list[TagInfo]:
        """Темы, по которым есть свободные задачи сложности rating."""
        async with self.session_factory() as session:
            rows = await TaskRepository(session).get_tags_with_free_tasks(rating)
        return [TagInfo(id=tag.id, name=tag.name, name_ru=tag.name_ru, free_count=count) for tag, count in rows]

    async def create_selection(self, rating: int, tag_id: int, size: int = SELECTION_SIZE) -> SelectionResult:
        """Выбирает до size свободных задач, создаёт подборку и закрепляет задачи за ней — в одной транзакции."""
        async with self.session_factory() as session, session.begin():
            selection_repo = SelectionRepository(session)
            tag = await selection_repo.get_tag(tag_id)
            if tag is None:
                raise UnknownTagError(tag_id)
            result = SelectionResult(
                rating=rating, tag=TagInfo(id=tag.id, name=tag.name, name_ru=tag.name_ru), requested=size
            )

            task_repo = TaskRepository(session)
            tasks = await task_repo.lock_free_tasks(rating, tag_id, size)
            if not tasks:
                return result

            selection = await selection_repo.create(rating, tag_id)
            await task_repo.assign_selection([task.id for task in tasks], selection.id)
            result.selection_id = selection.id
            result.tasks = [TaskInfo.model_validate(task) for task in tasks]

        logger.info("Подборка %d: rating=%d, tag=%s, задач %d", selection.id, rating, tag.name, len(tasks))
        return result
