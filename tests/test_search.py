import pytest

from schemas import TaskData
from services.search import QueryTooShortError, SearchKind, SearchService, parse_code
from tests.helpers import load_tasks, make_task


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("1700C", (1700, "C")),
        ("1700 c", (1700, "C")),
        ("1700/C", (1700, "C")),
        ("1700-C", (1700, "C")),
        ("  1700C  ", (1700, "C")),
        ("1526C2", (1526, "C2")),
        ("https://codeforces.com/problemset/problem/1700/C", (1700, "C")),
        ("https://codeforces.com/contest/1700/problem/C", (1700, "C")),
        ("1700", None),
        ("nature", None),
        ("abc 1700C", None),
    ],
)
def test_parse_code(query: str, expected: tuple[int, str] | None) -> None:
    assert parse_code(query) == expected


async def test_search_by_code_returns_full_info(real_tasks: list[TaskData]) -> None:
    result = await SearchService().search("1700 c")

    assert result.kind is SearchKind.CODE
    [task] = result.tasks
    assert task.code == "1700C"
    assert task.name == "Helping the Nature"
    assert task.rating == 1700
    assert task.solved_count == 12481
    assert task.tags == ["constructive algorithms", "data structures", "greedy"]
    assert task.url == "https://codeforces.com/problemset/problem/1700/C"


async def test_search_by_code_not_found(real_tasks: list[TaskData]) -> None:
    result = await SearchService().search("99999Z")

    assert result.kind is SearchKind.CODE
    assert result.tasks == []


async def test_search_by_contest(real_tasks: list[TaskData]) -> None:
    result = await SearchService().search("1700")

    assert result.kind is SearchKind.CONTEST
    assert [t.code for t in result.tasks] == ["1700A", "1700B", "1700C"]


async def test_search_by_name_is_case_insensitive_and_sorted(real_tasks: list[TaskData]) -> None:
    result = await SearchService().search("NATURE")

    assert result.kind is SearchKind.NAME
    assert [t.code for t in result.tasks] == ["1700C", "1223C", "1059D"]
    assert result.has_more is False


async def test_search_by_name_limit_and_has_more() -> None:
    await load_tasks([make_task(9000 + i, "A", f"String task {i}", solved_count=i) for i in range(12)])

    result = await SearchService().search("string", limit=10)

    assert len(result.tasks) == 10
    assert result.has_more is True
    assert result.tasks[0].name == "String task 11"


async def test_like_wildcards_are_escaped() -> None:
    await load_tasks([make_task(9100, "A", "100% Correct"), make_task(9101, "A", "1000 Problems")])

    result = await SearchService().search("100%")

    assert [t.name for t in result.tasks] == ["100% Correct"]


@pytest.mark.parametrize("query", ["x", "   ", ""])
async def test_too_short_query(query: str) -> None:
    with pytest.raises(QueryTooShortError):
        await SearchService().search(query)
