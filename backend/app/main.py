"""FastAPI application entry point.

Builds the app with a factory function rather than a module-level global so a
test can construct an isolated instance with its own configuration. ``uvicorn``
is pointed at the module-level ``app`` created at the bottom for convenience in
development.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import DomainError

#: Application logger. Uvicorn configures the root handler, so this inherits its
#: formatting and destination rather than installing a second logging setup.
logger = logging.getLogger("app")


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
            # Almost always empty. `Retry-After` on a 429 is the exception: when
            # to come back is part of the answer, and a header is where a client
            # looks for it.
            headers=exc.headers,
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

    # The last gap in the envelope, closed in Phase 10. An *unhandled* exception
    # was already safe -- Starlette answers `text/plain` "Internal Server Error"
    # and the traceback goes to the server log, never to the client -- but it was
    # the one response that did not match the shape `core/errors.py` promises,
    # and it is the one a client is least equipped to guess at.
    #
    # **What this handler must never do is describe the exception.** `str(exc)`
    # on a database error contains SQL and column names; on a filesystem error it
    # contains a path; on an error raised while handling a login it could contain
    # the submitted payload, which includes a password. So the message is a
    # constant. The detail goes to the log, where an operator can read it and a
    # caller cannot.
    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Something went wrong. Please try again.",
                }
            },
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
