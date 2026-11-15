from alembic import context
from sqlalchemy import create_engine

from backend.app.core.config import settings
from backend.app.infrastructure.database import models  # noqa: F401
from backend.app.infrastructure.database.session import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
