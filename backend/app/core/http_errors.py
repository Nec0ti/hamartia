"""HTTP exception handlers that avoid reflecting submitted values."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def safe_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Never serialize Pydantic's `input` field, which may contain credentials or study text."""
    return JSONResponse(status_code=422, content={"detail": "Invalid request"})
