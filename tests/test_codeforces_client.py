import httpx
import pytest
import respx

from clients.codeforces import CodeforcesAPIError, CodeforcesClient

URL = "https://codeforces.com/api/problemset.problems"

API_RESPONSE = {
    "status": "OK",
    "result": {
        "problems": [
            {
                "contestId": 1700,
                "index": "C",
                "name": "Helping the Nature",
                "type": "PROGRAMMING",
                "rating": 1700,
                "tags": ["constructive algorithms", "data structures", "greedy"],
            },
            {"contestId": 2100, "index": "A", "name": "Brand New Task", "type": "PROGRAMMING", "tags": []},
            {"contestId": 2101, "index": "B", "name": "No Statistics", "type": "PROGRAMMING", "rating": 900},
        ],
        "problemStatistics": [
            {"contestId": 1700, "index": "C", "solvedCount": 12481},
            {"contestId": 2100, "index": "A", "solvedCount": 5},
        ],
    },
}


@pytest.fixture
def client() -> CodeforcesClient:
    return CodeforcesClient(retry_delay=0)


async def test_fetch_tasks_joins_problems_with_statistics(client: CodeforcesClient, respx_mock: respx.Router) -> None:
    respx_mock.get(URL).mock(return_value=httpx.Response(200, json=API_RESPONSE))

    tasks = await client.fetch_tasks()

    assert [(t.cf_contest_id, t.index) for t in tasks] == [(1700, "C"), (2100, "A"), (2101, "B")]
    task_1700c = tasks[0]
    assert task_1700c.name == "Helping the Nature"
    assert task_1700c.rating == 1700
    assert task_1700c.solved_count == 12481
    assert task_1700c.tags == ["constructive algorithms", "data structures", "greedy"]
    # без rating -> None; нет статистики -> 0; нет tags -> []
    assert tasks[1].rating is None
    assert tasks[2].solved_count == 0
    assert tasks[2].tags == []


async def test_api_status_failed_raises(client: CodeforcesClient, respx_mock: respx.Router) -> None:
    respx_mock.get(URL).mock(return_value=httpx.Response(200, json={"status": "FAILED", "comment": "Call limit"}))

    with pytest.raises(CodeforcesAPIError, match="Call limit"):
        await client.fetch_tasks()


async def test_retries_on_server_error_then_succeeds(client: CodeforcesClient, respx_mock: respx.Router) -> None:
    route = respx_mock.get(URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=API_RESPONSE)],
    )

    tasks = await client.fetch_tasks()

    assert route.call_count == 2
    assert len(tasks) == 3


async def test_network_error_retried_until_limit(client: CodeforcesClient, respx_mock: respx.Router) -> None:
    route = respx_mock.get(URL).mock(side_effect=httpx.ConnectError("TLS handshake failed"))

    with pytest.raises(httpx.ConnectError):
        await client.fetch_tasks()
    assert route.call_count == client.retries


async def test_client_error_is_not_retried(client: CodeforcesClient, respx_mock: respx.Router) -> None:
    route = respx_mock.get(URL).mock(return_value=httpx.Response(404))

    with pytest.raises(httpx.HTTPStatusError):
        await client.fetch_tasks()
    assert route.call_count == 1
