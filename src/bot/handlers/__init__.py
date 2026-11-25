from bot.handlers import common, fallback, search, selection

# Порядок важен: кнопки меню и команды (common, selection) проверяются раньше режима поиска,
# который ловит любой текст; fallback — последним.
routers = [common.router, selection.router, search.router, fallback.router]

__all__ = ["routers"]
