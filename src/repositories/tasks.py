from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Tag, Task, task_tags
from schemas import TaskData

# asyncpg принимает не больше 32767 параметров в одном запросе: 1000 строк * 5 колонок укладываются с запасом.
BATCH_SIZE = 1000


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

    async def upsert_tags(self, names: list[str]) -> None:
        """Записывает теги в БД, уже существующие пропускает."""
        if not names:
            return

        stmt = insert(Tag).values([{"name": name} for name in names])
        stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
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
