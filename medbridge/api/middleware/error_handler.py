"""
Global Error Handling Middleware and Exception Handlers (TASK-28, Module M-03).

Constitutional Invariant Non-Negotiable #7:
"The backend must never return raw 500 errors to the patient. Unhandled exceptions
must be caught, logged server-side with stack traces, and converted into structured
ErrorResponse payloads containing pre-vetted clinically safe fallback messages."

Technical Specification Part II §9.
"""
from typing import Any, Optional

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from medbridge.api.schemas.responses import ErrorResponse
from medbridge.state.session_manager import SessionNotFoundError

logger = structlog.get_logger(__name__)

SAFE_FALLBACK = (
    "We're unable to process your question right now. "
    "For immediate health concerns, please contact your healthcare provider "
    "or call emergency services."
)


async def session_not_found_handler(
    request: Request,
    exc: SessionNotFoundError,
) -> JSONResponse:
    """Handle SessionNotFoundError, returning HTTP 404 with structured ErrorResponse."""
    logger.warning(
        "session_not_found",
        session_id=str(exc.session_id),
        path=request.url.path,
    )
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=ErrorResponse(
            error_code="SESSION_NOT_FOUND",
            message=f"Session {exc.session_id} not found.",
            safe_fallback=SAFE_FALLBACK,
        ).model_dump(mode="json"),
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle RequestValidationError, returning HTTP 422 with field-level details."""
    logger.warning(
        "request_validation_error",
        path=request.url.path,
        errors=exc.errors(),
    )
    return JSONResponse(
        status_code=getattr(
            status,
            "HTTP_422_UNPROCESSABLE_CONTENT",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
        content=ErrorResponse(
            error_code="VALIDATION_ERROR",
            message="Request validation failed.",
            details=exc.errors(),
            safe_fallback=SAFE_FALLBACK,
        ).model_dump(mode="json"),
    )


async def database_error_handler(
    request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    """Handle SQLAlchemy errors, returning HTTP 503 DATABASE_UNAVAILABLE."""
    logger.error(
        "database_unavailable",
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=ErrorResponse(
            error_code="DATABASE_UNAVAILABLE",
            message="Database service is currently unavailable.",
            safe_fallback=SAFE_FALLBACK,
        ).model_dump(mode="json"),
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Handle standard HTTP exceptions while preserving structured ErrorResponse format."""
    code_map = {
        status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
        status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
        status.HTTP_403_FORBIDDEN: "FORBIDDEN",
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
        status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
        status.HTTP_503_SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
    }
    error_code = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")

    logger.warning(
        "http_exception",
        status_code=exc.status_code,
        error_code=error_code,
        detail=str(exc.detail),
        path=request.url.path,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code=error_code,
            message=str(exc.detail),
            safe_fallback=SAFE_FALLBACK,
        ).model_dump(mode="json"),
    )


async def global_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Catch-all global exception handler (Non-Negotiable #7).

    Guarantees no raw 500 error pages or unhandled stack traces are returned to clients.
    Logs the full exception trace server-side and returns a structured ErrorResponse.
    """
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error_code="INTERNAL_ERROR",
            message="An internal error occurred.",
            safe_fallback=SAFE_FALLBACK,
        ).model_dump(mode="json"),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all global exception handlers onto a FastAPI application instance."""
    app.add_exception_handler(SessionNotFoundError, session_not_found_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(SQLAlchemyError, database_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
