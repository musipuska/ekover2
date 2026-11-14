from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.app.core.config import settings

connect_args = {}

if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}


engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    """Предоставляет сессию базы данных для API-запроса."""

    database = SessionLocal()

    try:
        yield database
    finally:
        database.close()

def ensure_schema(bind=None) -> list[str]:
    from sqlalchemy import inspect, text

    target = bind or engine
    inspector = inspect(target)
    added = []

    with target.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {item["name"] for item in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing or not column.nullable:
                    continue
                column_type = column.type.compile(dialect=target.dialect)
                connection.execute(
                    text(
                        f'ALTER TABLE {table.name} '
                        f'ADD COLUMN {column.name} {column_type}'
                    )
                )
                added.append(f"{table.name}.{column.name}")

    return added
