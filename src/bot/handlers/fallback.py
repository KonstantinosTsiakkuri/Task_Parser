import logging

from aiogram import Router
from aiogram.types import ErrorEvent, Message

from bot.keyboards import main_menu
from bot.texts import ERROR_TEXT, UNKNOWN_TEXT

logger = logging.getLogger(__name__)

router = Router(name="fallback")


@router.message()
async def on_unknown(message: Message) -> None:
    """Всё, что не поймали другие роутеры (подключается последним)."""
    await message.answer(UNKNOWN_TEXT, reply_markup=main_menu())


async def on_error(event: ErrorEvent) -> bool:
    """Глобальный обработчик ошибок: пишем traceback в лог, пользователю — короткое сообщение."""
    logger.exception("Ошибка при обработке апдейта %s", event.update.update_id, exc_info=event.exception)
    update = event.update
    try:
        if update.message is not None:
            await update.message.answer(ERROR_TEXT)
        elif update.callback_query is not None:
            await update.callback_query.answer(ERROR_TEXT, show_alert=True)
    except Exception:
        logger.exception("Не удалось сообщить пользователю об ошибке")
    return True
