"""Хендлеры вызываются напрямую: Telegram подменён моками, сервисы — настоящие, на тестовой БД."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InaccessibleMessage, Message
from sqlalchemy import select

from bot import texts
from bot.handlers import common, fallback, search, selection
from bot.keyboards import RatingCallback, TagCallback
from bot.states import SearchStates
from db.models import Tag
from db.session import async_session
from schemas import TaskData
from services.search import SearchService
from services.selection import SelectionService


def make_message(text: str = "") -> MagicMock:
    message = MagicMock(spec=Message)  # spec: isinstance(message, Message) -> True
    message.text = text
    message.answer = AsyncMock()
    message.edit_text = AsyncMock()
    return message


def make_callback(message: object | None = None) -> MagicMock:
    callback = MagicMock(spec=CallbackQuery)
    callback.message = make_message() if message is None else message
    callback.answer = AsyncMock()
    return callback


def sent_text(mock: AsyncMock) -> str:
    return str(mock.await_args.args[0])


@pytest.fixture
def state() -> AsyncMock:
    return AsyncMock(spec=FSMContext)


async def greedy_id() -> int:
    async with async_session() as session:
        value = await session.scalar(select(Tag.id).where(Tag.name == "greedy"))
    assert value is not None
    return value


async def test_start_help_cancel(state: AsyncMock) -> None:
    message = make_message("/start")
    await common.cmd_start(message, state)
    state.clear.assert_awaited()
    assert sent_text(message.answer) == texts.START_TEXT

    message = make_message("/help")
    await common.cmd_help(message)
    assert sent_text(message.answer) == texts.HELP_TEXT

    message = make_message("/cancel")
    await common.cmd_cancel(message, state)
    assert "Готово" in sent_text(message.answer)


async def test_selection_flow(real_tasks: list[TaskData], state: AsyncMock) -> None:
    service = SelectionService()

    message = make_message(texts.BTN_SELECTION)
    await selection.cmd_selection(message, state, service)
    assert sent_text(message.answer) == texts.CHOOSE_RATING
    keyboard = message.answer.await_args.kwargs["reply_markup"]
    assert keyboard.inline_keyboard[0][0].text == "800"

    callback = make_callback()
    await selection.on_rating(callback, RatingCallback(rating=1600), service)
    assert "Сложность <b>1600</b>" in sent_text(callback.message.edit_text)
    callback.answer.assert_awaited()

    callback = make_callback()
    await selection.on_tag(callback, TagCallback(rating=1600, tag_id=await greedy_id()), service)
    result_text = sent_text(callback.message.edit_text)
    assert "Подборка №1" in result_text
    assert "1526C2" in result_text and "1223C" in result_text
    assert "осталось только 2 из 10" in result_text

    # вторая попытка — задач больше нет, показываем кнопку «назад»
    callback = make_callback()
    await selection.on_tag(callback, TagCallback(rating=1600, tag_id=await greedy_id()), service)
    assert "свободных задач не осталось" in sent_text(callback.message.edit_text)
    assert callback.message.edit_text.await_args.kwargs["reply_markup"] is not None

    callback = make_callback()
    await selection.on_back_to_ratings(callback, service)
    assert sent_text(callback.message.edit_text) == texts.CHOOSE_RATING


async def test_selection_edge_cases(state: AsyncMock) -> None:
    service = SelectionService()  # БД пустая

    message = make_message()
    await selection.cmd_selection(message, state, service)
    assert sent_text(message.answer) == texts.NO_RATINGS

    callback = make_callback()
    await selection.on_back_to_ratings(callback, service)
    assert sent_text(callback.message.edit_text) == texts.NO_RATINGS

    callback = make_callback()
    await selection.on_rating(callback, RatingCallback(rating=1600), service)
    assert "свободных задач не осталось" in sent_text(callback.message.edit_text)

    callback = make_callback()
    await selection.on_tag(callback, TagCallback(rating=1600, tag_id=12345), service)
    assert callback.answer.await_args.kwargs["show_alert"] is True

    callback = make_callback(message=MagicMock(spec=InaccessibleMessage))
    await selection.on_tag(callback, TagCallback(rating=1600, tag_id=1), service)
    assert "устарело" in sent_text(callback.answer)


async def test_search_command_with_args(real_tasks: list[TaskData], state: AsyncMock) -> None:
    message = make_message("/search 1700C")
    command = CommandObject(prefix="/", command="search", args="1700C")

    await search.cmd_search(message, command, state, SearchService())

    assert "<b>1700C. Helping the Nature</b>" in sent_text(message.answer)
    state.set_state.assert_not_awaited()


async def test_search_mode(real_tasks: list[TaskData], state: AsyncMock) -> None:
    message = make_message("/search")
    await search.cmd_search(message, CommandObject(prefix="/", command="search"), state, SearchService())
    state.set_state.assert_awaited_with(SearchStates.waiting_query)
    assert sent_text(message.answer) == texts.SEARCH_PROMPT

    message = make_message(texts.BTN_SEARCH)
    await search.btn_search(message, state)
    assert sent_text(message.answer) == texts.SEARCH_PROMPT

    message = make_message("nature")
    await search.on_query(message, SearchService())
    assert "Найдено по запросу «nature»" in sent_text(message.answer)

    message = make_message("x")
    await search.on_query(message, SearchService())
    assert sent_text(message.answer) == texts.QUERY_TOO_SHORT


async def test_fallback_and_error_handler() -> None:
    message = make_message("привет")
    await fallback.on_unknown(message)
    assert sent_text(message.answer) == texts.UNKNOWN_TEXT

    event = MagicMock()
    event.update.message.answer = AsyncMock()
    assert await fallback.on_error(event) is True
    event.update.message.answer.assert_awaited_with(texts.ERROR_TEXT)

    event = MagicMock()
    event.update.message = None
    event.update.callback_query.answer = AsyncMock(side_effect=RuntimeError("telegram down"))
    assert await fallback.on_error(event) is True  # ошибка при уведомлении тоже не роняет бота
