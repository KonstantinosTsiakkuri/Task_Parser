import asyncio
import logging

from clients.codeforces import CodeforcesClient
from db.session import engine
from services.sync import SyncService


async def main() -> None:
    """Разовый прогон синхронизации (в блоке 3 здесь появится планировщик)."""
    try:
        await SyncService(CodeforcesClient()).sync()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    asyncio.run(main())
