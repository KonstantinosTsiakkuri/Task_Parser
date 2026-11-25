"""add pg_trgm index on task name

Revision ID: 5ba349784255
Revises: 437c339b3bb3
Create Date: 2026-11-18 16:44:30.291338

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ba349784255'
down_revision: Union[str, Sequence[str], None] = '437c339b3bb3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # autogenerate не видит расширения PostgreSQL — создаём вручную до индекса, который от него зависит
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        "ix_tasks_name_trgm",
        "tasks",
        ["name"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_tasks_name_trgm", table_name="tasks", postgresql_using="gin")
    # расширение не удаляем: им могут пользоваться другие объекты БД
