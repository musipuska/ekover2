"""Baseline: текущая схема метаданных.

Revision ID: 0001
Revises:
"""
from alembic import op

from backend.app.infrastructure.database import models  # noqa: F401
from backend.app.infrastructure.database.session import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # create_all пропускает уже существующие таблицы, поэтому baseline безопасен
    # и для чистой БД, и для БД, созданной ensure_schema() ранее.
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
