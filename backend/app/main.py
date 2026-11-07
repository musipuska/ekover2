from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import api_router
from backend.app.core.config import settings
from backend.app.core.logging import setup_logging
from backend.app.infrastructure.database.session import (
    Base,
    engine
)

# Импорт моделей необходим для регистрации таблиц SQLAlchemy.
from backend.app.infrastructure.database import models  # noqa: F401


setup_logging()

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    description="Backend системы экологического мониторинга ЭКОВЕР",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    api_router,
    prefix=settings.API_PREFIX
)


@app.get("/")
def root():
    """Главная проверочная страница API."""

    return {
        "project": "ЭКОВЕР",
        "status": "running",
        "documentation": "/docs"
    }