from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.texts import BTN_HELP, BTN_SEARCH, BTN_SELECTION
from schemas import TagInfo

RATINGS_PER_ROW = 4
TAGS_PER_ROW = 2


class RatingCallback(CallbackData, prefix="rating"):
    """Нажата кнопка сложности: callback_data = 'rating:1600'."""

    rating: int


class TagCallback(CallbackData, prefix="tag"):
    """Нажата кнопка темы: callback_data = 'tag:1600:22' (сложность, tags.id)."""

    rating: int
    tag_id: int


class BackToRatingsCallback(CallbackData, prefix="ratings"):
    """Вернуться к выбору сложности."""


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SELECTION), KeyboardButton(text=BTN_SEARCH)],
            [KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
    )


def ratings_keyboard(ratings: list[int]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for rating in ratings:
        builder.button(text=str(rating), callback_data=RatingCallback(rating=rating))
    builder.adjust(RATINGS_PER_ROW)
    return builder.as_markup()


def tags_keyboard(rating: int, tags: list[TagInfo]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for tag in tags:
        builder.button(
            text=f"{tag.title} ({tag.free_count})",
            callback_data=TagCallback(rating=rating, tag_id=tag.id),
        )
    builder.adjust(TAGS_PER_ROW)
    builder.row(back_button())
    return builder.as_markup()


def back_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="« Другая сложность", callback_data=BackToRatingsCallback().pack())


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[back_button()]])
