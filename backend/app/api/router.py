
from fastapi import APIRouter

from backend.app.api.v1 import (
    health,
    datasets,
    uploads,
    jobs,
    profiles,
    quality,
)


api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(datasets.router)
api_router.include_router(uploads.router)
api_router.include_router(jobs.router)
api_router.include_router(profiles.router)
api_router.include_router(quality.router)
