from bot import texts
from bot.keyboards import RatingCallback, TagCallback, main_menu, ratings_keyboard, tags_keyboard
from schemas import TagInfo, TaskInfo
from services.search import SearchKind, SearchResult
from services.selection import SelectionResult

TASK_1700C = TaskInfo(
    cf_contest_id=1700,
    index="C",
    name="Helping the Nature",
    rating=1700,
    solved_count=12481,
    tags=["greedy", "constructive algorithms", "data structures"],
)
TASK_ESCAPE = TaskInfo(cf_contest_id=1, index="A", name="a < b & c", rating=None, solved_count=0, tags=[])
GREEDY = TagInfo(id=22, name="greedy", name_ru="Жадные алгоритмы", free_count=198)


def test_task_info_sorts_tags_and_builds_links() -> None:
    assert TASK_1700C.tags == ["constructive algorithms", "data structures", "greedy"]
    assert TASK_1700C.code == "1700C"
    assert TASK_1700C.url == "https://codeforces.com/problemset/problem/1700/C"


def test_tag_title_prefers_russian_name() -> None:
    assert GREEDY.title == "Жадные алгоритмы"
    assert TagInfo(id=1, name="new tag").title == "new tag"
    assert texts.tag_title("dp") == "Динамическое программирование"
    assert texts.tag_title("unknown") == "unknown"


def test_format_task_line_and_card() -> None:
    line = texts.format_task_line(1, TASK_1700C)
    assert line.startswith('1. <a href="https://codeforces.com/problemset/problem/1700/C"><b>1700C</b>')
    assert "⭐ 1700 · ✅ 12 481 · Конструктив, Структуры данных, Жадные алгоритмы" in line

    card = texts.format_task_card(TASK_1700C)
    assert "<b>1700C. Helping the Nature</b>" in card
    assert "Решили: 12 481" in card


def test_html_is_escaped_and_missing_values_shown() -> None:
    assert "a &lt; b &amp; c" in texts.format_task_line(1, TASK_ESCAPE)
    assert "⭐ —" in texts.format_task_line(1, TASK_ESCAPE)
    card = texts.format_task_card(TASK_ESCAPE)
    assert "Сложность: не указана" in card and "Темы: не указаны" in card


def test_format_selection_variants() -> None:
    full = SelectionResult(rating=1600, tag=GREEDY, selection_id=9, tasks=[TASK_1700C] * 10)
    assert "Подборка №9" in texts.format_selection(full)
    assert "неполная" not in texts.format_selection(full)

    partial = SelectionResult(rating=1600, tag=GREEDY, selection_id=10, tasks=[TASK_1700C] * 3)
    assert "осталось только 3 из 10" in texts.format_selection(partial)

    empty = SelectionResult(rating=1600, tag=GREEDY)
    assert "свободных задач не осталось" in texts.format_selection(empty)


def test_format_search_variants() -> None:
    assert texts.format_search(SearchResult("99999Z", SearchKind.CODE)) == "Задача «99999Z» не найдена."
    assert texts.format_search(SearchResult("99999", SearchKind.CONTEST)) == "Контест 99999 не найден."
    assert "ничего не найдено" in texts.format_search(SearchResult("<x>", SearchKind.NAME))
    assert "&lt;x&gt;" in texts.format_search(SearchResult("<x>", SearchKind.NAME))

    assert "<b>1700C. Helping the Nature</b>" in texts.format_search(
        SearchResult("1700C", SearchKind.CODE, [TASK_1700C])
    )
    assert "Контест <b>1700</b>, задач: 1" in texts.format_search(
        SearchResult("1700", SearchKind.CONTEST, [TASK_1700C])
    )
    by_name = texts.format_search(SearchResult("nature", SearchKind.NAME, [TASK_1700C], has_more=True))
    assert "Найдено по запросу «nature»" in by_name
    assert "уточните запрос" in by_name


def test_split_text_respects_limit() -> None:
    text = "\n".join(f"line {i}" for i in range(100))
    chunks = texts.split_text(text, limit=50)
    assert all(len(chunk) <= 50 for chunk in chunks)
    assert "\n".join(chunks) == text
    assert texts.split_text("short") == ["short"]


def test_keyboards() -> None:
    menu = main_menu()
    assert [b.text for row in menu.keyboard for b in row] == [texts.BTN_SELECTION, texts.BTN_SEARCH, texts.BTN_HELP]

    ratings = ratings_keyboard([800, 900, 1000, 1100, 1200])
    assert [len(row) for row in ratings.inline_keyboard] == [4, 1]
    assert ratings.inline_keyboard[0][0].callback_data == RatingCallback(rating=800).pack() == "rating:800"

    tags = tags_keyboard(1600, [GREEDY])
    assert tags.inline_keyboard[0][0].text == "Жадные алгоритмы (198)"
    assert tags.inline_keyboard[0][0].callback_data == TagCallback(rating=1600, tag_id=22).pack() == "tag:1600:22"
    assert tags.inline_keyboard[-1][0].callback_data == "ratings"
