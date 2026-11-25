from sqlalchemy import func, select, text, update

from db.models import Tag, Task, task_tags
from db.session import async_session
from repositories.tasks import BATCH_SIZE
from schemas import TaskData
from tests.helpers import REAL_TASKS, load_tasks, make_task


async def count(model_or_table: object) -> int:
    async with async_session() as session:
        return await session.scalar(select(func.count()).select_from(model_or_table)) or 0  # type: ignore[arg-type]


async def test_sync_writes_tasks_tags_and_links(real_tasks: list[TaskData]) -> None:
    assert await count(Task) == len(REAL_TASKS)
    unique_tags = {tag for task in REAL_TASKS for tag in task.tags}
    assert await count(Tag) == len(unique_tags)
    assert await count(task_tags) == sum(len(task.tags) for task in REAL_TASKS)

    async with async_session() as session:
        task = await session.scalar(select(Task).where(Task.cf_contest_id == 1700, Task.index == "C"))
        assert task is not None
        assert (task.name, task.rating, task.solved_count) == ("Helping the Nature", 1700, 12481)


async def test_sync_fills_russian_tag_names(real_tasks: list[TaskData]) -> None:
    async with async_session() as session:
        greedy = await session.scalar(select(Tag).where(Tag.name == "greedy"))
    assert greedy is not None
    assert greedy.name_ru == "Жадные алгоритмы"


async def test_unknown_tag_keeps_null_name_ru() -> None:
    await load_tasks([make_task(3000, "A", tags=["brand new tag"])])
    async with async_session() as session:
        tag = await session.scalar(select(Tag).where(Tag.name == "brand new tag"))
    assert tag is not None
    assert tag.name_ru is None


async def test_repeated_sync_does_not_duplicate(real_tasks: list[TaskData]) -> None:
    before = (await count(Task), await count(Tag), await count(task_tags))

    returned = await load_tasks(REAL_TASKS)

    assert returned == len(REAL_TASKS)
    assert (await count(Task), await count(Tag), await count(task_tags)) == before


async def test_sync_updates_fields_but_keeps_selection(real_tasks: list[TaskData]) -> None:
    async with async_session() as session, session.begin():
        await session.execute(text("INSERT INTO selections (rating, tag_id) VALUES (1700, 1)"))
        await session.execute(update(Task).where(Task.cf_contest_id == 1700, Task.index == "C").values(selection_id=1))

    changed = make_task(1700, "C", "Helping the Nature", 1800, ["greedy"], 13000)
    await load_tasks([changed])

    async with async_session() as session:
        task = await session.scalar(select(Task).where(Task.cf_contest_id == 1700, Task.index == "C"))
    assert task is not None
    assert (task.rating, task.solved_count, task.selection_id) == (1800, 13000, 1)


async def test_duplicates_in_api_response_are_merged() -> None:
    first = make_task(3000, "A", solved_count=1)
    second = make_task(3000, "A", solved_count=2)

    returned = await load_tasks([first, second])

    assert returned == 1
    async with async_session() as session:
        assert await session.scalar(select(Task.solved_count)) == 2


async def test_sync_handles_more_rows_than_batch_size() -> None:
    tasks = [make_task(10_000 + i, "A", tags=["greedy", "math"]) for i in range(BATCH_SIZE + 5)]

    await load_tasks(tasks)

    assert await count(Task) == BATCH_SIZE + 5
    assert await count(task_tags) == 2 * (BATCH_SIZE + 5)
