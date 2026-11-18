import re
from dataclasses import dataclass, field
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.session import async_session
from repositories.tasks import TaskRepository
from schemas import TaskInfo

SEARCH_LIMIT = 10
MIN_QUERY_LENGTH = 2

# 1700C, 1700 C, 1700/C, 1700-c, 1526C2, а также ссылки .../problemset/problem/1700/C и .../contest/1700/problem/C
CODE_RE = re.compile(r"^(?:.*/(?:problem|contest)/)?(\d+)\s*(?:/problem/|[\s/\-])?\s*([A-Za-z]\d?)/?$")
CONTEST_RE = re.compile(r"^\d+$")


class SearchKind(StrEnum):
    CODE = "code"
    CONTEST = "contest"
    NAME = "name"


@dataclass
class SearchResult:
    """Результат поиска. has_more — по названию нашлось больше, чем показано."""

    query: str
    kind: SearchKind
    tasks: list[TaskInfo] = field(default_factory=list)
    has_more: bool = False


class QueryTooShortError(Exception):
    """Запрос короче MIN_QUERY_LENGTH символов."""


def parse_code(query: str) -> tuple[int, str] | None:
    """'1700 c' -> (1700, 'C'); не номер задачи -> None."""
    match = CODE_RE.match(query.strip())
    if match is None:
        return None
    return int(match.group(1)), match.group(2).upper()


class SearchService:
    """Поиск задач по номеру (1700C), номеру контеста (1700) или части названия."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] = async_session) -> None:
        self.session_factory = session_factory

    async def search(self, query: str, limit: int = SEARCH_LIMIT) -> SearchResult:
        query = " ".join(query.split())
        if len(query) < MIN_QUERY_LENGTH and not query.isdigit():
            raise QueryTooShortError(query)

        async with self.session_factory() as session:
            repo = TaskRepository(session)

            code = parse_code(query)
            if code is not None:
                task = await repo.get_by_code(*code)
                tasks = [task] if task is not None else []
                return SearchResult(query, SearchKind.CODE, [TaskInfo.model_validate(t) for t in tasks])

            if CONTEST_RE.match(query):
                tasks = await repo.get_by_contest(int(query))
                return SearchResult(query, SearchKind.CONTEST, [TaskInfo.model_validate(t) for t in tasks])

            # берём на одну больше лимита, чтобы узнать, есть ли ещё результаты
            tasks = await repo.search_by_name(query, limit + 1)
            return SearchResult(
                query,
                SearchKind.NAME,
                [TaskInfo.model_validate(t) for t in tasks[:limit]],
                has_more=len(tasks) > limit,
            )
