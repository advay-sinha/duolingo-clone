"""FastAPI application entry point.

Builds the app with a factory function rather than a module-level global so a
test can construct an isolated instance with its own configuration. ``uvicorn``
is pointed at the module-level ``app`` created at the bottom for convenience in
development.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings


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

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
