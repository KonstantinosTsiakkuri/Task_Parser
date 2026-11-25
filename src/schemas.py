from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

CF_TASK_URL = "https://codeforces.com/problemset/problem/{contest_id}/{index}"


class TaskData(BaseModel):
    """Задача Codeforces в виде, пригодном для записи в БД."""

    cf_contest_id: int
    index: str
    name: str
    rating: int | None = None
    tags: list[str] = Field(default_factory=list)
    solved_count: int = 0


class TaskInfo(BaseModel):
    """Полная информация о задаче для показа пользователю (строится из ORM-объекта Task)."""

    model_config = ConfigDict(from_attributes=True)

    cf_contest_id: int
    index: str
    name: str
    rating: int | None
    solved_count: int
    tags: list[str]

    @field_validator("tags", mode="before")
    @classmethod
    def _tag_names(cls, value: Any) -> list[str]:
        """Task.tags — список ORM-объектов Tag, нам нужны их имена по алфавиту."""
        return sorted(tag if isinstance(tag, str) else tag.name for tag in value)

    @property
    def code(self) -> str:
        """Номер задачи в привычном виде: 1700C."""
        return f"{self.cf_contest_id}{self.index}"

    @property
    def url(self) -> str:
        return CF_TASK_URL.format(contest_id=self.cf_contest_id, index=self.index)


class TagInfo(BaseModel):
    """Тег для клавиатуры бота: сколько по нему свободных задач выбранной сложности."""

    id: int
    name: str
    name_ru: str | None = None
    free_count: int = 0

    @property
    def title(self) -> str:
        return self.name_ru or self.name
