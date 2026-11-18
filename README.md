# Task Parser — задачи Codeforces в Telegram

Дипломный проект SkyPro (Backend). Сервис раз в час забирает архив задач [Codeforces](https://codeforces.com/problemset)
в PostgreSQL, а Telegram-бот выдаёт по ним тренировочные подборки и ищет задачи.

## Возможности

- **Синхронизация с Codeforces** — номер, название, сложность (rating), темы (теги), количество решивших;
  обновление раз в час (`SYNC_IN_MIN`), без дублей (upsert).
- **Подборки из 10 задач** — пользователь выбирает сложность и тему. Подборки не пересекаются: каждая задача
  попадает максимум в одну подборку (`tasks.selection_id`), в том числе при одновременных запросах
  (`SELECT ... FOR UPDATE SKIP LOCKED`).
- **Поиск** — по номеру (`1700C`, `1700 C`, `1700/C`, ссылка на задачу), по номеру контеста (`1700`) и по части
  названия (`nature`, триграммный индекс `pg_trgm`). Выводится вся информация о задаче и ссылка.
- Русские названия тем на кнопках.

## Стек

Python 3.13 · aiogram 3 · SQLAlchemy 2 (async) + asyncpg · PostgreSQL 18 · Alembic · httpx · APScheduler 3 ·
Redis (FSM бота) · pydantic-settings · Docker / docker-compose · pytest + pytest-asyncio + respx · GitHub Actions.

## Архитектура

```
src/
├── main_bot.py           точка входа бота (polling)
├── main_worker.py        точка входа воркера (синхронизация по расписанию)
├── config.py             настройки из .env (pydantic-settings)
├── schemas.py            DTO: TaskData, TaskInfo, TagInfo
├── bot/                  Telegram: хендлеры, клавиатуры, тексты, FSM
├── scheduler/jobs.py     задача APScheduler
├── services/             бизнес-логика: sync, selection, search
├── repositories/         SQL-запросы (не коммитят — транзакцией управляет сервис)
├── clients/codeforces.py HTTP-клиент Codeforces API
└── db/                   модели SQLAlchemy и сессия
migrations/               миграции Alembic
tests/                    тесты (отдельная тестовая БД)
```

Зависимости слоёв идут только вниз: `bot → services → repositories + clients → db`; `scheduler → services`.

Таблицы: `tasks` (задачи, `selection_id` — в какую подборку выдана), `tags` (темы, `name_ru`),
`task_tags` (связь многие-ко-многим), `selections` (выданные подборки: сложность, тема, время).

## Переменные окружения

Скопируйте `.env.example` в `.env` и заполните:

| Переменная | Пример | Описание |
|---|---|---|
| `BOT_TOKEN` | `123456:ABC...` | токен бота от [@BotFather](https://t.me/BotFather) |
| `DB_NAME` | `task_parser` | имя базы |
| `DB_USER` | `postgres` | пользователь PostgreSQL |
| `DB_PASSWORD` | — | пароль PostgreSQL |
| `DB_HOST` | `localhost` | хост БД (в docker-compose подменяется на `db`) |
| `DB_PORT` | `5432` | порт БД |
| `REDIS_HOST` | `localhost` | хост Redis (в docker-compose — `redis`) |
| `REDIS_PORT` | `6379` | порт Redis |
| `SYNC_IN_MIN` | `60` | интервал синхронизации, минуты |

## Запуск через Docker Compose

Нужен только Docker.

```powershell
copy .env.example .env      # и заполнить BOT_TOKEN, DB_PASSWORD
docker compose up -d --build
docker compose ps -a        # migrate: Exited (0), остальные: running
docker compose logs -f bot
```

Сервисы: `db` (PostgreSQL, порт 5433 на хосте), `redis`, `migrate` (`alembic upgrade head`, завершается),
`worker` (синхронизация сразу и раз в `SYNC_IN_MIN` минут), `bot`.
Остановка — `docker compose stop`, удаление контейнеров — `docker compose down` (`-v` удалит и данные).

## Локальный запуск

Нужны Python 3.13, [Poetry](https://python-poetry.org/) 2.x и PostgreSQL; Redis необязателен (без него
состояния бота хранятся в памяти).

```powershell
poetry install
copy .env.example .env               # заполнить
poetry run alembic upgrade head      # создать таблицы
poetry run python src/main_worker.py # воркер: первая синхронизация (~11.5 тыс. задач) сразу, затем раз в час
poetry run python src/main_bot.py    # бот (в другом терминале)
```

Не запускайте бота одновременно локально и в Docker с одним токеном — Telegram отдаёт обновления только одному.

## Команды бота

| Команда / кнопка | Действие |
|---|---|
| `/start` | приветствие и меню |
| `/selection`, «🎯 Подборка» | выбор сложности → темы → подборка из 10 задач |
| `/search 1700C` | сразу найти задачу |
| `/search`, «🔍 Поиск» | режим поиска: каждое сообщение — запрос |
| `/cancel` | выйти из режима поиска |
| `/help` | справка |

## Тесты и линтеры

Тесты используют отдельную БД `task_parser_test` (создаётся и мигрируется автоматически при каждом запуске;
имя можно задать переменной `TEST_DB_NAME`, оно обязано оканчиваться на `_test`). Сеть не нужна: Codeforces API
замокан через respx, Telegram — через unittest.mock.

```powershell
poetry run pytest --cov=src --cov-report=term-missing --cov-fail-under=75

poetry run isort src tests
poetry run black src tests
poetry run flake8 src tests
poetry run mypy src
```

CI (GitHub Actions, `.github/workflows/ci.yml`) на каждый push и pull request запускает линтеры и тесты
с сервисом PostgreSQL.
