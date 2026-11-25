import asyncio

import pytest
from sqlalchemy import func, select

from db.models import Selection, Tag, Task
from db.session import async_session
from services.selection import SELECTION_SIZE, SelectionService, UnknownTagError
from tests.helpers import load_tasks, make_task


async def tag_id(name: str) -> int:
    async with async_session() as session:
        value = await session.scalar(select(Tag.id).where(Tag.name == name))
    assert value is not None
    return value


@pytest.fixture
async def greedy_1600() -> int:
    """12 задач greedy сложности 1600 (solved_count по убыванию), 3 задачи dp 1600 и 1 задача 2000."""
    tasks = [make_task(5000 + i, "A", f"Greedy {i}", 1600, ["greedy"], 1000 - i) for i in range(12)]
    tasks += [make_task(6000 + i, "B", f"Dp {i}", 1600, ["dp"], 50) for i in range(3)]
    tasks.append(make_task(7000, "C", "Hard greedy", 2000, ["greedy"], 10))
    await load_tasks(tasks)
    return await tag_id("greedy")


async def test_ratings_and_tags_lists(greedy_1600: int) -> None:
    service = SelectionService()

    assert await service.get_ratings() == [1600, 2000]
    tags = await service.get_tags(1600)
    assert [(t.name, t.free_count) for t in tags] == [("greedy", 12), ("dp", 3)]
    assert tags[0].title == "Жадные алгоритмы"


async def test_selection_returns_10_most_solved_tasks(greedy_1600: int) -> None:
    result = await SelectionService().create_selection(1600, greedy_1600)

    assert result.selection_id is not None
    assert result.is_complete and not result.is_empty
    assert len(result.tasks) == SELECTION_SIZE
    assert [t.code for t in result.tasks] == [f"{5000 + i}A" for i in range(10)]
    assert all(t.rating == 1600 and "greedy" in t.tags for t in result.tasks)
    assert result.tag.name_ru == "Жадные алгоритмы"

    async with async_session() as session:
        assigned = await session.scalar(select(func.count()).where(Task.selection_id == result.selection_id))
    assert assigned == SELECTION_SIZE


async def test_selections_do_not_overlap_and_run_out(greedy_1600: int) -> None:
    service = SelectionService()

    first = await service.create_selection(1600, greedy_1600)
    second = await service.create_selection(1600, greedy_1600)
    third = await service.create_selection(1600, greedy_1600)

    assert len(second.tasks) == 2 and not second.is_complete
    assert {t.code for t in first.tasks}.isdisjoint({t.code for t in second.tasks})
    assert third.is_empty and third.selection_id is None
    async with async_session() as session:
        assert await session.scalar(select(func.count()).select_from(Selection)) == 2
    # свободных greedy 1600 не осталось — тема пропала из списка
    assert [t.name for t in await service.get_tags(1600)] == ["dp"]


async def test_parallel_selections_never_share_tasks(greedy_1600: int) -> None:
    service = SelectionService()

    results = await asyncio.gather(*(service.create_selection(1600, greedy_1600, size=3) for _ in range(4)))

    codes = [t.code for r in results for t in r.tasks]
    assert len(codes) == 12
    assert len(set(codes)) == 12


async def test_unknown_tag_raises(greedy_1600: int) -> None:
    with pytest.raises(UnknownTagError):
        await SelectionService().create_selection(1600, 999_999)


async def test_no_ratings_when_everything_is_taken() -> None:
    await load_tasks([make_task(8000, "A", rating=800)])
    service = SelectionService()
    await service.create_selection(800, await tag_id("greedy"))

    assert await service.get_ratings() == []
    assert await service.get_tags(800) == []
