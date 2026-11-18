from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InaccessibleMessage, Message

from bot.keyboards import (
    BackToRatingsCallback,
    RatingCallback,
    TagCallback,
    back_keyboard,
    ratings_keyboard,
    tags_keyboard,
)
from bot.texts import BTN_SELECTION, CHOOSE_RATING, NO_RATINGS, choose_tag_text, format_selection, no_tags_text
from services.selection import SelectionService, UnknownTagError

router = Router(name="selection")


@router.message(Command("selection"))
@router.message(F.text == BTN_SELECTION)
async def cmd_selection(message: Message, state: FSMContext, selection_service: SelectionService) -> None:
    """Шаг 1: список сложностей, по которым ещё есть свободные задачи."""
    await state.clear()
    ratings = await selection_service.get_ratings()
    if not ratings:
        await message.answer(NO_RATINGS)
        return
    await message.answer(CHOOSE_RATING, reply_markup=ratings_keyboard(ratings))


@router.callback_query(BackToRatingsCallback.filter())
async def on_back_to_ratings(callback: CallbackQuery, selection_service: SelectionService) -> None:
    ratings = await selection_service.get_ratings()
    if isinstance(callback.message, Message):
        if ratings:
            await callback.message.edit_text(CHOOSE_RATING, reply_markup=ratings_keyboard(ratings))
        else:
            await callback.message.edit_text(NO_RATINGS)
    await callback.answer()


@router.callback_query(RatingCallback.filter())
async def on_rating(
    callback: CallbackQuery, callback_data: RatingCallback, selection_service: SelectionService
) -> None:
    """Шаг 2: темы со свободными задачами выбранной сложности."""
    tags = await selection_service.get_tags(callback_data.rating)
    if isinstance(callback.message, Message):
        if tags:
            await callback.message.edit_text(
                choose_tag_text(callback_data.rating), reply_markup=tags_keyboard(callback_data.rating, tags)
            )
        else:
            await callback.message.edit_text(no_tags_text(callback_data.rating), reply_markup=back_keyboard())
    await callback.answer()


@router.callback_query(TagCallback.filter())
async def on_tag(callback: CallbackQuery, callback_data: TagCallback, selection_service: SelectionService) -> None:
    """Шаг 3: собираем подборку и заменяем клавиатуру результатом (повторно нажать ту же кнопку нельзя)."""
    message = callback.message
    if message is None or isinstance(message, InaccessibleMessage):
        await callback.answer("Сообщение устарело, начните заново: /selection", show_alert=True)
        return

    try:
        result = await selection_service.create_selection(callback_data.rating, callback_data.tag_id)
    except UnknownTagError:
        await callback.answer("Такой темы больше нет, начните заново: /selection", show_alert=True)
        return

    await message.edit_text(format_selection(result), reply_markup=back_keyboard() if result.is_empty else None)
    await callback.answer()
