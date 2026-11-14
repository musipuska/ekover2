import uuid
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def ok(data, **extra) -> dict:
    return {
        "status": "success",
        "data": data,
        "metadata": {
            "request_id": uuid.uuid4().hex,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            **extra,
        },
    }


async def api_error_handler(request: Request, error: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "status": "error",
            "error": {"code": error.code, "message": error.message, "details": error.details},
        },
    )
