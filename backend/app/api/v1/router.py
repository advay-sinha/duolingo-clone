"""Aggregates every v1 route module into a single router.

``main.py`` mounts this one object under ``/api/v1``. Adding an endpoint means
writing a route module and including it here -- the application factory never
changes.
"""

from fastapi import APIRouter

from app.api.v1.routes import auth, courses, health, leaderboard, lessons, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(courses.router)
api_router.include_router(lessons.router)
api_router.include_router(leaderboard.router)
api_router.include_router(users.router)
