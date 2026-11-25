from aiogram.fsm.state import State, StatesGroup


class SearchStates(StatesGroup):
    """Режим поиска: каждое текстовое сообщение пользователя — поисковый запрос, пока не /cancel."""

    waiting_query = State()
