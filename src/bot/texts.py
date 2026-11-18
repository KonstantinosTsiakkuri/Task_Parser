"""Тексты сообщений бота. Чистые функции без обращения к Telegram — легко тестировать."""

from html import escape

from schemas import TaskInfo
from services.search import SearchKind, SearchResult
from services.selection import SelectionResult
from services.tag_names import TAG_NAMES_RU

MESSAGE_LIMIT = 4096

BTN_SELECTION = "🎯 Подборка"
BTN_SEARCH = "🔍 Поиск"
BTN_HELP = "❓ Помощь"

START_TEXT = (
    "Привет! Я помогаю тренироваться на задачах Codeforces.\n\n"
    f"{BTN_SELECTION} — выберите сложность и тему, и я соберу 10 задач. "
    "Каждая задача выдаётся только в одну подборку, поэтому подборки не повторяются.\n"
    f"{BTN_SEARCH} — найду задачу по номеру (1700C) или по части названия.\n\n"
    "Задачи обновляются с Codeforces раз в час."
)

HELP_TEXT = (
    "<b>Команды</b>\n"
    "/selection — собрать подборку из 10 задач\n"
    "/search — режим поиска; можно сразу: <code>/search 1700C</code>\n"
    "/cancel — выйти из режима поиска\n"
    "/help — эта справка\n\n"
    "<b>Что понимает поиск</b>\n"
    "<code>1700C</code>, <code>1700 C</code>, <code>1700/C</code> — задача по номеру\n"
    "ссылка на задачу Codeforces — тоже номер\n"
    "<code>1700</code> — все задачи контеста\n"
    "<code>nature</code> — поиск по части названия (до 10 задач)"
)

SEARCH_PROMPT = (
    "Режим поиска. Отправьте номер задачи (<code>1700C</code>), номер контеста (<code>1700</code>) "
    "или часть названия. Выйти — /cancel."
)
CHOOSE_RATING = "Выберите сложность:"
NO_RATINGS = "Свободных задач не осталось — все задачи уже розданы в подборки."
UNKNOWN_TEXT = f"Не понял запрос. Нажмите {BTN_SELECTION} или {BTN_SEARCH}, или /help."
QUERY_TOO_SHORT = "Слишком короткий запрос — нужно хотя бы 2 символа."
ERROR_TEXT = "Что-то пошло не так. Попробуйте ещё раз чуть позже."


def tag_title(name: str) -> str:
    """Русское название темы, если оно есть в словаре."""
    return TAG_NAMES_RU.get(name, name)


def format_number(value: int) -> str:
    """12481 -> '12 481'."""
    return f"{value:,}".replace(",", " ")


def choose_tag_text(rating: int) -> str:
    return f"Сложность <b>{rating}</b>. Выберите тему (в скобках — сколько свободных задач):"


def no_tags_text(rating: int) -> str:
    return f"Для сложности <b>{rating}</b> свободных задач не осталось. Выберите другую сложность."


def format_task_line(number: int, task: TaskInfo) -> str:
    """Строка задачи в списке: номер, название-ссылка, сложность, решившие, темы."""
    rating = task.rating if task.rating is not None else "—"
    tags = ", ".join(tag_title(tag) for tag in task.tags) or "без тем"
    return (
        f'{number}. <a href="{task.url}"><b>{task.code}</b> {escape(task.name)}</a>\n'
        f"    ⭐ {rating} · ✅ {format_number(task.solved_count)} · {escape(tags)}"
    )


def format_task_card(task: TaskInfo) -> str:
    """Полная карточка одной задачи."""
    rating = task.rating if task.rating is not None else "не указана"
    tags = ", ".join(tag_title(tag) for tag in task.tags) or "не указаны"
    return (
        f"<b>{task.code}. {escape(task.name)}</b>\n\n"
        f"Контест: {task.cf_contest_id}, задача {task.index}\n"
        f"Сложность: {rating}\n"
        f"Решили: {format_number(task.solved_count)}\n"
        f"Темы: {escape(tags)}\n\n"
        f'<a href="{task.url}">Открыть на Codeforces</a>'
    )


def format_selection(result: SelectionResult) -> str:
    topic = escape(result.tag.title)
    if result.is_empty:
        return (
            f"По теме «{topic}» со сложностью <b>{result.rating}</b> свободных задач не осталось. "
            "Выберите другую тему или сложность."
        )
    lines = [f"🎯 <b>Подборка №{result.selection_id}</b> · сложность {result.rating} · {topic}", ""]
    lines += [format_task_line(number, task) for number, task in enumerate(result.tasks, start=1)]
    if not result.is_complete:
        lines += [
            "",
            f"⚠️ Свободных задач по этой теме осталось только {len(result.tasks)} "
            f"из {result.requested} — подборка неполная.",
        ]
    return "\n".join(lines)


def format_search(result: SearchResult) -> str:
    query = escape(result.query)
    if not result.tasks:
        if result.kind is SearchKind.CODE:
            return f"Задача «{query}» не найдена."
        if result.kind is SearchKind.CONTEST:
            return f"Контест {query} не найден."
        return f"По запросу «{query}» ничего не найдено."

    if result.kind is SearchKind.CODE:
        return format_task_card(result.tasks[0])

    if result.kind is SearchKind.CONTEST:
        header = f"Контест <b>{query}</b>, задач: {len(result.tasks)}"
    else:
        header = f"Найдено по запросу «{query}»:"
    lines = [header, ""]
    lines += [format_task_line(number, task) for number, task in enumerate(result.tasks, start=1)]
    if result.has_more:
        lines += ["", f"Показаны первые {len(result.tasks)} — уточните запрос, чтобы увидеть остальные."]
    return "\n".join(lines)


def split_text(text: str, limit: int = MESSAGE_LIMIT) -> list[str]:
    """Режет длинный текст на сообщения по границам строк (лимит Telegram — 4096 символов)."""
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = line
    if current:
        chunks.append(current)
    return chunks
