"""Тестовые данные и клиент Codeforces без сети."""

from clients.codeforces import CodeforcesClient
from schemas import TaskData
from services.sync import SyncService


def make_task(
    contest_id: int,
    index: str,
    name: str = "Task",
    rating: int | None = 1600,
    tags: list[str] | None = None,
    solved_count: int = 0,
) -> TaskData:
    return TaskData(
        cf_contest_id=contest_id,
        index=index,
        name=name,
        rating=rating,
        tags=tags if tags is not None else ["greedy"],
        solved_count=solved_count,
    )


# Реальные задачи Codeforces (как в нашей БД) + задача без сложности и без тегов
REAL_TASKS = [
    make_task(1700, "A", "Optimal Path", 800, ["constructive algorithms", "greedy", "math"], 23810),
    make_task(1700, "B", "Palindromic Numbers ", 1100, ["constructive algorithms", "implementation", "math"], 20233),
    make_task(1700, "C", "Helping the Nature", 1700, ["constructive algorithms", "data structures", "greedy"], 12481),
    make_task(1223, "C", "Save the Nature", 1600, ["binary search", "greedy"], 10063),
    make_task(1059, "D", "Nature Reserve", 2200, ["binary search", "geometry", "ternary search"], 3102),
    make_task(1526, "C2", "Potions (Hard Version)", 1600, ["data structures", "greedy"], 33724),
    make_task(2100, "A", "Brand New Task", None, [], 5),
]


class FakeCodeforcesClient(CodeforcesClient):
    """Клиент без сети: отдаёт заранее заданный список задач."""

    def __init__(self, tasks: list[TaskData]) -> None:
        super().__init__()
        self.tasks = tasks

    async def fetch_tasks(self) -> list[TaskData]:
        return list(self.tasks)


async def load_tasks(tasks: list[TaskData]) -> int:
    """Загружает задачи в тестовую БД настоящим SyncService."""
    return await SyncService(client=FakeCodeforcesClient(tasks)).sync()
