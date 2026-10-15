"""One error shape for the whole API.

Every failure, whether a missing row, a bad request body, or an
unexpected crash, leaves the API as ``{"error": {code, message, details}}``.
"""

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.api.schemas import ErrorDetail, ErrorResponse


def _envelope(code: str, message: str, details: dict | None = None) -> dict:
    return ErrorResponse(
        error=ErrorDetail(code=code, message=message, details=details)
    ).model_dump()


async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    codes = {400: "bad_request", 404: "not_found", 409: "conflict"}
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(codes.get(exc.status_code, "http_error"), str(exc.detail)),
    )


async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_envelope(
            "validation_error",
            "Request validation failed",
            {"errors": jsonable_encoder(exc.errors())},
        ),
    )


async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=_envelope("internal_error", "An unexpected error occurred"),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, _http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_handler)
