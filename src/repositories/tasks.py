from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Tag, Task, task_tags
from schemas import TaskData

# asyncpg принимает не больше 32767 параметров в одном запросе: 1000 строк * 5 колонок укладываются с запасом.
BATCH_SIZE = 1000


def escape_like(value: str) -> str:
    """Экранирует спецсимволы LIKE, чтобы ввод пользователя «100%» искался буквально."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class TaskRepository:
    """Запись задач, тегов и связей между ними. Транзакцией управляет вызывающий код (репозиторий не коммитит)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_tasks(self, tasks: list[TaskData]) -> None:
        """Записывает задачи в БД: новые добавляет, существующие обновляет (selection_id не трогаем)."""
        rows = [task.model_dump(exclude={"tags"}) for task in tasks]

        for start in range(0, len(rows), BATCH_SIZE):
            batch = rows[start : start + BATCH_SIZE]
            stmt = insert(Task).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["cf_contest_id", "index"],
                set_={
                    "name": stmt.excluded.name,
                    "rating": stmt.excluded.rating,
                    "solved_count": stmt.excluded.solved_count,
                },
            )
            await self.session.execute(stmt)

    async def upsert_tags(self, names: list[str], names_ru: dict[str, str] | None = None) -> None:
        """Записывает теги в БД. У существующих обновляет русское название, если оно известно."""
        if not names:
            return

        names_ru = names_ru or {}
        stmt = insert(Tag).values([{"name": name, "name_ru": names_ru.get(name)} for name in names])
        stmt = stmt.on_conflict_do_update(
            index_elements=["name"],
            # новый тег без перевода не затирает перевод, заданный раньше
            set_={"name_ru": func.coalesce(stmt.excluded.name_ru, Tag.name_ru)},
        )
        await self.session.execute(stmt)

    async def link_tags(self, tasks: list[TaskData]) -> None:
        """Записывает связи «задача — тег» в task_tags, уже существующие пропускает."""
        tag_rows = await self.session.execute(select(Tag.id, Tag.name))
        tag_ids: dict[str, int] = {name: tag_id for tag_id, name in tag_rows.all()}

        task_rows = await self.session.execute(select(Task.id, Task.cf_contest_id, Task.index))
        task_ids: dict[tuple[int, str], int] = {
            (contest_id, index): task_id for task_id, contest_id, index in task_rows.all()
        }

        rows: list[dict[str, Any]] = []
        for task in tasks:
            task_id = task_ids[(task.cf_contest_id, task.index)]
            for tag_name in task.tags:
                rows.append({"task_id": task_id, "tag_id": tag_ids[tag_name]})

        for start in range(0, len(rows), BATCH_SIZE):
            batch = rows[start : start + BATCH_SIZE]
            stmt = insert(task_tags).values(batch)
            stmt = stmt.on_conflict_do_nothing(index_elements=["task_id", "tag_id"])
            await self.session.execute(stmt)

    async def get_free_ratings(self) -> list[int]:
        """Сложности, по которым есть хотя бы одна свободная задача (selection_id IS NULL)."""
        stmt = (
            select(Task.rating)
            .where(Task.rating.is_not(None), Task.selection_id.is_(None))
            .distinct()
            .order_by(Task.rating)
        )
        result = await self.session.scalars(stmt)
        return [rating for rating in result.all() if rating is not None]

    async def get_tags_with_free_tasks(self, rating: int) -> list[tuple[Tag, int]]:
        """Теги, у которых есть свободные задачи сложности rating, с их количеством (по убыванию)."""
        free_count = func.count(Task.id).label("free_count")
        stmt = (
            select(Tag, free_count)
            .join(task_tags, task_tags.c.tag_id == Tag.id)
            .join(Task, Task.id == task_tags.c.task_id)
            .where(Task.rating == rating, Task.selection_id.is_(None))
            .group_by(Tag.id)
            .order_by(free_count.desc(), Tag.name)
        )
        result = await self.session.execute(stmt)
        return [(tag, count) for tag, count in result.tuples().all()]

    async def lock_free_tasks(self, rating: int, tag_id: int, limit: int) -> list[Task]:
        """Выбирает до limit свободных задач нужной сложности и темы и блокирует их строки до конца транзакции.

        SKIP LOCKED: строки, уже заблокированные параллельной транзакцией (кто-то собирает такую же подборку
        прямо сейчас), пропускаются — поэтому две подборки никогда не получат одну и ту же задачу.
        """
        stmt = (
            select(Task)
            .join(task_tags, task_tags.c.task_id == Task.id)
            .where(task_tags.c.tag_id == tag_id, Task.rating == rating, Task.selection_id.is_(None))
            .order_by(Task.solved_count.desc(), Task.id)
            .limit(limit)
            .with_for_update(of=Task, skip_locked=True)
            .options(selectinload(Task.tags))
        )
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_by_code(self, contest_id: int, index: str) -> Task | None:
        """Задача по номеру: (1700, "C") -> 1700C. Использует уникальный индекс (cf_contest_id, index)."""
        stmt = (
            select(Task).where(Task.cf_contest_id == contest_id, Task.index == index).options(selectinload(Task.tags))
        )
        return await self.session.scalar(stmt)

    async def get_by_contest(self, contest_id: int) -> list[Task]:
        """Все задачи контеста по порядку: 1700A, 1700B, ..."""
        stmt = (
            select(Task).where(Task.cf_contest_id == contest_id).order_by(Task.index).options(selectinload(Task.tags))
        )
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def search_by_name(self, query: str, limit: int) -> list[Task]:
        """Поиск по подстроке в названии без учёта регистра (ILIKE '%query%'), самые решаемые — первыми."""
        pattern = "%" + escape_like(query) + "%"
        stmt = (
            select(Task)
            .where(Task.name.ilike(pattern, escape="\\"))
            .order_by(Task.solved_count.desc(), Task.id)
            .limit(limit)
            .options(selectinload(Task.tags))
        )
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def assign_selection(self, task_ids: list[int], selection_id: int) -> None:
        """Помечает задачи как выданные в подборку selection_id."""
        if not task_ids:
            return
        stmt = update(Task).where(Task.id.in_(task_ids)).values(selection_id=selection_id)
        await self.session.execute(stmt)
