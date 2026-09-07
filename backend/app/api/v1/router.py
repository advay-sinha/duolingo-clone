"""Aggregates every v1 route module into a single router.

``main.py`` mounts this one object under ``/api/v1``. Adding an endpoint in a
later phase means writing a route module and including it here — the application
factory never changes.
"""

from fastapi import APIRouter

from app.api.v1.routes import health

api_router = APIRouter()
api_router.include_router(health.router)
