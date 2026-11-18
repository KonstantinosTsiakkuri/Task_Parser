import asyncio
import logging
from datetime import timedelta
from unittest.mock import MagicMock

import httpx
import pytest
from sqlalchemy.exc import OperationalError

import main_worker
from clients.codeforces import CodeforcesAPIError
from scheduler import jobs


def test_create_scheduler_configures_sync_job() -> None:
    scheduler = jobs.create_scheduler(60)

    job = scheduler.get_job(jobs.SYNC_JOB_ID)
    assert job is not None
    assert job.func is jobs.sync_tasks_job
    assert job.trigger.interval == timedelta(minutes=60)
    assert job.max_instances == 1
    assert job.coalesce is True
    assert job.next_run_time is not None  # первый запуск сразу при старте


class FakeSyncService:
    error: BaseException | None = None

    async def sync(self) -> int:
        if self.error is not None:
            raise self.error
        return 11526


@pytest.fixture
def fake_sync(monkeypatch: pytest.MonkeyPatch) -> type[FakeSyncService]:
    FakeSyncService.error = None
    monkeypatch.setattr(jobs, "SyncService", FakeSyncService)
    return FakeSyncService


async def test_job_logs_success(fake_sync: type[FakeSyncService], caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="scheduler.jobs"):
        await jobs.sync_tasks_job()
    assert "Синхронизировано задач: 11526" in caplog.text


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (httpx.ConnectError("boom"), "Codeforces недоступен"),
        (CodeforcesAPIError("Call limit exceeded"), "Codeforces недоступен"),
        (OperationalError("SELECT 1", {}, Exception("db down")), "Ошибка БД"),
        (ValueError("unexpected"), "Непредвиденная ошибка"),
    ],
)
async def test_job_swallows_errors(
    fake_sync: type[FakeSyncService], caplog: pytest.LogCaptureFixture, error: BaseException, message: str
) -> None:
    fake_sync.error = error
    with caplog.at_level(logging.ERROR, logger="scheduler.jobs"):
        await jobs.sync_tasks_job()  # не падает
    assert message in caplog.text


async def test_worker_starts_scheduler_and_stops_on_event(monkeypatch: pytest.MonkeyPatch) -> None:
    scheduler = MagicMock()
    monkeypatch.setattr(main_worker, "create_scheduler", MagicMock(return_value=scheduler))
    stop_event = asyncio.Event()

    task = asyncio.create_task(main_worker.main(stop_event))
    await asyncio.sleep(0.05)
    scheduler.start.assert_called_once()
    assert not task.done()

    stop_event.set()
    await asyncio.wait_for(task, timeout=5)
    scheduler.shutdown.assert_called_once_with(wait=False)
