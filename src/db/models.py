from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    name_ru: Mapped[str | None] = mapped_column(String(100))


class Selection(Base):
    __tablename__ = "selections"

    id: Mapped[int] = mapped_column(primary_key=True)
    rating: Mapped[int]
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


task_tags = Table(
    "task_tags",
    Base.metadata,
    Column("task_id", ForeignKey("tasks.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True, index=True),
)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("cf_contest_id", "index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cf_contest_id: Mapped[int]
    index: Mapped[str]
    name: Mapped[str]
    rating: Mapped[int | None] = mapped_column(index=True)
    solved_count: Mapped[int] = mapped_column(default=0)
    selection_id: Mapped[int | None] = mapped_column(ForeignKey("selections.id"), index=True)
    tags: Mapped[list[Tag]] = relationship(secondary=task_tags)
