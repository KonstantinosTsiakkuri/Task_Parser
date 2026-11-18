import asyncio
import logging
from typing import Any

import httpx

from schemas import TaskData

logger = logging.getLogger(__name__)


class CodeforcesAPIError(Exception):
    """Codeforces ответил status != OK."""


class CodeforcesClient:
    """HTTP-клиент к публичному API Codeforces."""

    BASE_URL = "https://codeforces.com/api"

    def __init__(self, timeout: float = 30, retries: int = 3, retry_delay: float = 2) -> None:
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = retry_delay

    async def _get(self, method: str) -> httpx.Response:
        """GET с повторами при сетевых сбоях и ответах 5xx (Codeforces иногда рвёт TLS-соединение)."""
        url = f"{self.BASE_URL}/{method}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(1, self.retries + 1):
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    return response
                except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                    retryable = isinstance(exc, httpx.TransportError) or exc.response.status_code >= 500
                    if not retryable or attempt == self.retries:
                        raise
                    logger.warning("Запрос %s не удался (%r), попытка %d/%d", method, exc, attempt, self.retries)
                    await asyncio.sleep(self.retry_delay * attempt)
        raise AssertionError("unreachable")  # pragma: no cover

    async def fetch_raw_tasks(self) -> dict[str, Any]:
        """Возвращает поле result ответа problemset.problems: {"problems": [...], "problemStatistics": [...]}."""
        response = await self._get("problemset.problems")
        data: dict[str, Any] = response.json()

        if data.get("status") != "OK":
            raise CodeforcesAPIError(data.get("comment", "unknown error"))
        result: dict[str, Any] = data["result"]
        return result

    async def fetch_tasks(self) -> list[TaskData]:
        """Скачивает все задачи и склеивает их с количеством решивших по ключу (contestId, index)."""
        raw = await self.fetch_raw_tasks()

        solved_counts = {(stat["contestId"], stat["index"]): stat["solvedCount"] for stat in raw["problemStatistics"]}

        tasks = []
        for item in raw["problems"]:
            key = (item["contestId"], item["index"])
            tasks.append(
                TaskData(
                    cf_contest_id=item["contestId"],
                    index=item["index"],
                    name=item["name"],
                    rating=item.get("rating"),
                    tags=item.get("tags", []),
                    solved_count=solved_counts.get(key, 0),
                )
            )
        return tasks
