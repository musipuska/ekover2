
from fastapi import APIRouter

from backend.app.api.v1 import (
    analytics,
    datasets,
    health,
    jobs,
    ml,
    profiles,
    quality,
    uploads,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(datasets.router)
api_router.include_router(uploads.router)
api_router.include_router(jobs.router)
api_router.include_router(profiles.router)
api_router.include_router(quality.router)
api_router.include_router(analytics.router)
api_router.include_router(ml.router)
