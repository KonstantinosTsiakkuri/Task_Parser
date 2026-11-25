import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot.handlers import routers
from bot.handlers.fallback import on_error
from bot.storage import create_storage
from config import settings
from db.session import engine
from logging_config import setup_logging
from services.search import SearchService
from services.selection import SelectionService

logger = logging.getLogger(__name__)

COMMANDS = [
    BotCommand(command="selection", description="Подборка из 10 задач"),
    BotCommand(command="search", description="Поиск задачи"),
    BotCommand(command="cancel", description="Выйти из режима поиска"),
    BotCommand(command="help", description="Справка"),
]


async def main() -> None:
    bot = Bot(
        token=settings.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    storage = await create_storage(settings.REDIS_HOST, settings.REDIS_PORT)

    # именованные аргументы Dispatcher попадают в хендлеры по имени параметра (selection_service, search_service)
    dp = Dispatcher(storage=storage, selection_service=SelectionService(), search_service=SearchService())
    dp.include_routers(*routers)
    dp.errors.register(on_error)

    try:
        me = await bot.get_me()
        logger.info("Бот @%s запущен (polling)", me.username)
        await bot.set_my_commands(COMMANDS)
        await dp.start_polling(bot)
    finally:
        await storage.close()
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    setup_logging()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
