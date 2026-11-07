from fastapi import APIRouter


router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    """Проверяет, работает ли API."""

    return {
        "status": "ok",
        "message": "Ekover API работает."
    }