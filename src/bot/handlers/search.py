from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.states import SearchStates
from bot.texts import BTN_SEARCH, QUERY_TOO_SHORT, SEARCH_PROMPT, format_search, split_text
from services.search import QueryTooShortError, SearchService

router = Router(name="search")


async def send_search_result(message: Message, query: str, search_service: SearchService) -> None:
    try:
        result = await search_service.search(query)
    except QueryTooShortError:
        await message.answer(QUERY_TOO_SHORT)
        return
    for chunk in split_text(format_search(result)):
        await message.answer(chunk)


@router.message(Command("search"))
async def cmd_search(
    message: Message, command: CommandObject, state: FSMContext, search_service: SearchService
) -> None:
    """/search 1700C — сразу ищем; просто /search — включаем режим поиска."""
    if command.args:
        await send_search_result(message, command.args, search_service)
        return
    await state.set_state(SearchStates.waiting_query)
    await message.answer(SEARCH_PROMPT)


@router.message(F.text == BTN_SEARCH)
async def btn_search(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchStates.waiting_query)
    await message.answer(SEARCH_PROMPT)


@router.message(SearchStates.waiting_query, F.text)
async def on_query(message: Message, search_service: SearchService) -> None:
    """В режиме поиска каждое сообщение — запрос; режим остаётся включённым до /cancel."""
    await send_search_result(message, message.text or "", search_service)
