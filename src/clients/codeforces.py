from typing import Any

import httpx

from schemas import TaskData


class CodeforcesAPIError(Exception):
    """Codeforces ответил status != OK."""


class CodeforcesClient:
    """HTTP-клиент к публичному API Codeforces."""

    BASE_URL = "https://codeforces.com/api"

    def __init__(self, timeout: float = 30) -> None:
        self.timeout = timeout

    async def fetch_raw_tasks(self) -> dict[str, Any]:
        """Возвращает поле result ответа problemset.problems: {"problems": [...], "problemStatistics": [...]}."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.BASE_URL}/problemset.problems")
            response.raise_for_status()
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
