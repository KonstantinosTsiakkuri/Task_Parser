from pydantic import BaseModel, Field


class TaskData(BaseModel):
    """Задача Codeforces в виде, пригодном для записи в БД."""

    cf_contest_id: int
    index: str
    name: str
    rating: int | None = None
    tags: list[str] = Field(default_factory=list)
    solved_count: int = 0
