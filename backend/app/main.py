"""FastAPI application entry point.

Builds the app with a factory function rather than a module-level global so a
test can construct an isolated instance with its own configuration. ``uvicorn``
is pointed at the module-level ``app`` created at the bottom for convenience in
development.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import DomainError


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construct and configure the FastAPI application.

    Args:
        settings: Optional override, used by tests to supply their own config.
            Defaults to the cached process-wide settings.
    """
    settings = settings or get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
    )

    # The browser blocks a page served from http://localhost:3000 from reading a
    # response from http://localhost:8000 unless that response carries the right
    # CORS headers — different port means different origin. This middleware adds
    # them for the explicitly listed development origins only.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # One handler turns every domain error into an HTTP response. Services raise
    # meaning ("this course does not exist"); this decides the status code. The
    # mapping lives in one place, and every error body has the same shape, so the
    # frontend's ApiError has exactly one thing to parse.
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    # FastAPI's own errors do not use the domain envelope by default: a
    # validation failure returns `{"detail": [...]}` with pydantic internals
    # (the offending input echoed back, error contexts), and an unmatched route
    # returns `{"detail": "Not Found"}`. Two more handlers put them in the same
    # `{"error": {"code", "message"}}` shape, so the envelope claim in
    # `core/errors.py` is true of *every* response and the frontend has one
    # thing to parse.
    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # The field path is useful; the echoed input is not, and could reflect
        # a client's payload straight back into an error body.
        first = exc.errors()[0] if exc.errors() else None
        where = ".".join(str(part) for part in first["loc"]) if first else "request"
        detail = first["msg"] if first else "Invalid request."
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": f"{where}: {detail}",
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        _: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "http_error",
                    "message": str(exc.detail),
                }
            },
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
