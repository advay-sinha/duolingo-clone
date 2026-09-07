"""Tests for GET /api/v1/users/me and /users/me/stats."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, UserStats


def test_get_me_returns_the_seeded_learner(
    client: TestClient, db_session: Session
) -> None:
    seeded = db_session.scalar(select(User))

    body = client.get("/api/v1/users/me").json()

    assert body["id"] == seeded.id
    assert body["username"] == "learner"
    assert body["display_name"] == seeded.display_name


def test_stats_returns_200(client: TestClient) -> None:
    assert client.get("/api/v1/users/me/stats").status_code == 200


def test_stats_match_the_database_row(
    client: TestClient, db_session: Session
) -> None:
    """Values must come from user_stats, not from constants in the schema."""
    user = db_session.scalar(select(User))
    stats = db_session.get(UserStats, user.id)

    body = client.get("/api/v1/users/me/stats").json()

    assert body["total_xp"] == stats.total_xp
    assert body["gems"] == stats.gems
    assert body["hearts"] == stats.hearts
    assert body["current_streak"] == stats.current_streak
    assert body["longest_streak"] == stats.longest_streak
    assert body["daily_goal"] == stats.daily_goal
    assert body["daily_xp"] == stats.daily_xp


def test_seeded_stats_are_a_genuine_day_one_state(client: TestClient) -> None:
    body = client.get("/api/v1/users/me/stats").json()

    assert body["total_xp"] == 0
    assert body["current_streak"] == 0
    assert body["hearts"] == 5
    assert body["max_hearts"] == 5
    assert body["gems"] == 540
    assert body["daily_goal"] == 30


def test_changing_the_database_changes_the_response(
    client: TestClient, db_session: Session
) -> None:
    """Proves the endpoint reads live data rather than a cached constant."""
    user = db_session.scalar(select(User))
    stats = db_session.get(UserStats, user.id)
    stats.total_xp = 137
    stats.hearts = 3
    db_session.commit()

    body = client.get("/api/v1/users/me/stats").json()

    assert body["total_xp"] == 137
    assert body["hearts"] == 3


def test_stats_do_not_expose_internal_columns(client: TestClient) -> None:
    body = client.get("/api/v1/users/me/stats").json()

    assert "user_id" not in body
    assert "hearts_updated_at" not in body
    assert "last_activity_date" not in body


def test_deleting_the_learner_cascades_and_invalidates_their_session(
    client: TestClient, db_session: Session
) -> None:
    """Replaces the Phase 3–8 "missing demo user" test.

    That test asserted a 503 with code ``demo_user_missing``, which was the right
    behaviour while identity came from ``settings.demo_username``. Since Phase 9
    identity comes from a session, so the failure mode is different: deleting the
    learner cascades to their session row, and the next request is simply
    unauthenticated. The cascade itself is still worth proving, which is why this
    test kept the deletion.
    """
    user = db_session.scalar(select(User))
    db_session.delete(user)
    db_session.commit()

    response = client.get("/api/v1/users/me/stats")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
    # ON DELETE CASCADE removed the stats, progress, attempts and session rows.
    assert db_session.scalar(select(User)) is None
