"""Tests for GET /api/v1/courses."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course


def test_list_courses_returns_200(client: TestClient) -> None:
    assert client.get("/api/v1/courses").status_code == 200


def test_the_seeded_course_appears(client: TestClient, db_session: Session) -> None:
    """The response must come from the database, not from a constant."""
    seeded = db_session.scalar(select(Course))

    body = client.get("/api/v1/courses").json()

    assert len(body["courses"]) == 1
    course = body["courses"][0]
    assert course["id"] == seeded.id
    assert course["title"] == seeded.title
    assert course["source_language"] == "English"
    assert course["target_language"] == "Spanish"


def test_the_response_does_not_expose_internal_fields(client: TestClient) -> None:
    """The API schema is a contract, not a dump of the table.

    ``slug`` is an internal natural key used by the seed, and ``created_at`` is
    bookkeeping. Neither is any use to a client, and exposing them would make
    them de-facto API surface that a future refactor could not change.
    """
    course = client.get("/api/v1/courses").json()["courses"][0]

    assert "slug" not in course
    assert "created_at" not in course
    assert "units" not in course
    assert set(course) == {
        "id",
        "title",
        "description",
        "source_language",
        "target_language",
        "flag_emoji",
    }
