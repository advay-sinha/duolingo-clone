"""Tests for the health endpoint.

Uses FastAPI's TestClient, which drives the ASGI app in-process — no server is
started and no port is bound, so the test is fast and cannot collide with a
running dev server.
"""

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_health_returns_ok() -> None:
    """The endpoint responds 200 with the documented body."""
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_is_mounted_under_the_versioned_prefix() -> None:
    """The unversioned path is not served, guarding the /api/v1 contract."""
    assert client.get("/health").status_code == 404


def test_cors_headers_are_returned_for_the_frontend_origin() -> None:
    """A request from the dev frontend origin is allowed by CORS.

    This is the behaviour the browser depends on; without it the frontend's
    fetch would fail even though the endpoint itself works.
    """
    response = client.get(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_does_not_allow_an_unlisted_origin() -> None:
    """An origin that is not configured gets no allow header."""
    response = client.get(
        "/api/v1/health",
        headers={"Origin": "http://evil.example"},
    )

    assert "access-control-allow-origin" not in response.headers
