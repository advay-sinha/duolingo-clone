"""Leaderboard, profile and achievement API tests."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Achievement,
    LessonAttempt,
    User,
    UserAchievement,
    UserSkillProgress,
    UserStats,
)
from app.services import achievement_service

from tests.conftest import make_user

# --------------------------------------------------------------------------
# Leaderboard
# --------------------------------------------------------------------------


def test_leaderboard_returns_the_single_seeded_learner(
    client: TestClient, db_session: Session
) -> None:
    """One learner is shown as one learner. No filler opponents."""
    body = client.get("/api/v1/leaderboard").json()

    assert len(body["entries"]) == 1
    assert body["entries"][0]["rank"] == 1
    assert body["entries"][0]["is_current_user"] is True
    assert body["current_user_rank"] == 1


def test_leaderboard_states_its_period_and_metric(client: TestClient) -> None:
    """The screen labels itself from the response rather than assuming."""
    body = client.get("/api/v1/leaderboard").json()

    assert body["period"] == "all-time"
    assert body["metric"] == "total_xp"


def test_leaderboard_orders_by_xp_descending(
    client: TestClient, db_session: Session
) -> None:
    learner = db_session.scalar(select(User))
    db_session.get(UserStats, learner.id).total_xp = 50

    for name, xp in [("ana", 300), ("bo", 120), ("cy", 10)]:
        rival = make_user(username=name, display_name=name.title())
        db_session.add(rival)
        db_session.flush()
        db_session.add(UserStats(user_id=rival.id, total_xp=xp))
    db_session.commit()

    body = client.get("/api/v1/leaderboard").json()
    xps = [entry["xp"] for entry in body["entries"]]

    assert xps == sorted(xps, reverse=True)
    assert xps == [300, 120, 50, 10]
    assert [e["rank"] for e in body["entries"]] == [1, 2, 3, 4]


def test_the_current_learner_is_flagged_wherever_they_rank(
    client: TestClient, db_session: Session
) -> None:
    learner = db_session.scalar(select(User))
    db_session.get(UserStats, learner.id).total_xp = 5

    rival = make_user(username="ana", display_name="Ana")
    db_session.add(rival)
    db_session.flush()
    db_session.add(UserStats(user_id=rival.id, total_xp=999))
    db_session.commit()

    body = client.get("/api/v1/leaderboard").json()
    flagged = [e for e in body["entries"] if e["is_current_user"]]

    assert len(flagged) == 1
    assert flagged[0]["user_id"] == learner.id
    assert body["current_user_rank"] == 2


def test_leaderboard_ties_are_ordered_stably(
    client: TestClient, db_session: Session
) -> None:
    """Equal XP must not shuffle between requests."""
    learner = db_session.scalar(select(User))
    db_session.get(UserStats, learner.id).total_xp = 100
    rival = make_user(username="ana", display_name="Ana")
    db_session.add(rival)
    db_session.flush()
    db_session.add(UserStats(user_id=rival.id, total_xp=100))
    db_session.commit()

    first = [e["user_id"] for e in client.get("/api/v1/leaderboard").json()["entries"]]
    second = [e["user_id"] for e in client.get("/api/v1/leaderboard").json()["entries"]]

    assert first == second


def test_leaderboard_does_not_expose_internal_user_fields(
    client: TestClient,
) -> None:
    """The one screen where one learner's data is shown to another."""
    entry = client.get("/api/v1/leaderboard").json()["entries"][0]

    assert set(entry) == {
        "rank",
        "user_id",
        "display_name",
        "avatar_url",
        "xp",
        "current_streak",
        "is_current_user",
    }
    assert "username" not in entry
    assert "created_at" not in entry


# --------------------------------------------------------------------------
# Profile
# --------------------------------------------------------------------------


def test_profile_returns_identity_stats_and_aggregates(
    client: TestClient, db_session: Session
) -> None:
    body = client.get("/api/v1/users/me/profile").json()

    assert body["user"]["username"] == "learner"
    assert body["stats"]["hearts"] == 5
    assert body["lessons_completed"] == 0
    assert body["skills_completed"] == 0
    assert body["total_crowns"] == 0
    assert body["perfect_lessons"] == 0


def test_profile_aggregates_are_counted_from_persisted_state(
    client: TestClient, db_session: Session
) -> None:
    user = db_session.scalar(select(User))
    db_session.add_all(
        [
            LessonAttempt(
                user_id=user.id,
                lesson_id=1,
                completed=True,
                completed_at=datetime.now(timezone.utc),
                correct_answers=5,
                incorrect_answers=0,
            ),
            LessonAttempt(
                user_id=user.id,
                lesson_id=2,
                completed=True,
                completed_at=datetime.now(timezone.utc),
                correct_answers=4,
                incorrect_answers=1,
            ),
        ]
    )
    progress = db_session.scalar(
        select(UserSkillProgress).where(UserSkillProgress.user_id == user.id)
    )
    progress.crowns = 1
    db_session.commit()

    body = client.get("/api/v1/users/me/profile").json()

    assert body["lessons_completed"] == 2
    assert body["perfect_lessons"] == 1  # only the one with no mistakes
    assert body["skills_completed"] == 1
    assert body["total_crowns"] == 1


# --------------------------------------------------------------------------
# Achievements
# --------------------------------------------------------------------------


def test_the_catalogue_is_seeded_and_starts_locked(
    client: TestClient,
) -> None:
    body = client.get("/api/v1/users/me/achievements").json()

    assert body["total_count"] == 6
    assert body["unlocked_count"] == 0
    assert all(item["unlocked"] is False for item in body["achievements"])
    assert all(item["unlocked_at"] is None for item in body["achievements"])


def test_locked_achievements_still_describe_what_to_do(
    client: TestClient,
) -> None:
    """Locked entries show the requirement in words, not as machine-readable
    condition data."""
    items = client.get("/api/v1/users/me/achievements").json()["achievements"]
    first = items[0]

    assert first["title"]
    assert first["description"]
    assert "predicate" not in first
    assert "requirement" not in first


def test_completing_a_lesson_unlocks_the_first_achievements(
    client: TestClient, db_session: Session
) -> None:
    from tests.test_api_lessons import answer_all_correctly, complete, first_lesson, start

    lesson = first_lesson(db_session)
    attempt = start(client, lesson.id)["attempt_id"]
    answer_all_correctly(client, db_session, lesson, attempt)
    result = complete(client, lesson.id, attempt).json()

    # Reported on the completion response so the celebration screen can say so.
    assert "First steps" in result["achievements_unlocked"]
    assert "Flawless" in result["achievements_unlocked"]

    body = client.get("/api/v1/users/me/achievements").json()
    unlocked = {i["key"] for i in body["achievements"] if i["unlocked"]}

    assert "FIRST_LESSON" in unlocked
    assert "PERFECT_LESSON" in unlocked
    assert "STREAK_7" not in unlocked


def test_a_lesson_with_a_mistake_does_not_unlock_the_perfect_award(
    client: TestClient, db_session: Session
) -> None:
    from tests.test_api_lessons import (
        answer,
        complete,
        correct_payload,
        first_lesson,
        start,
        wrong_payload,
    )

    lesson = first_lesson(db_session)
    attempt = start(client, lesson.id)["attempt_id"]
    answer(client, lesson.id, attempt, lesson.exercises[0], wrong_payload(lesson.exercises[0]))
    for exercise in lesson.exercises[1:]:
        answer(client, lesson.id, attempt, exercise, correct_payload(exercise))
    result = complete(client, lesson.id, attempt).json()

    assert "First steps" in result["achievements_unlocked"]
    assert "Flawless" not in result["achievements_unlocked"]


def test_evaluation_is_idempotent(client: TestClient, db_session: Session) -> None:
    """The mandatory idempotency check: evaluating repeatedly awards once."""
    user = db_session.scalar(select(User))
    db_session.add(
        LessonAttempt(
            user_id=user.id,
            lesson_id=1,
            completed=True,
            completed_at=datetime.now(timezone.utc),
            correct_answers=5,
        )
    )
    db_session.commit()

    first = achievement_service.evaluate(db_session, user)
    second = achievement_service.evaluate(db_session, user)
    third = achievement_service.evaluate(db_session, user)
    db_session.commit()

    assert len(first) >= 1
    assert second == []
    assert third == []

    rows = db_session.scalars(
        select(UserAchievement).where(UserAchievement.user_id == user.id)
    ).all()
    assert len(rows) == len(first)


def test_the_database_blocks_a_duplicate_award(db_session: Session) -> None:
    """UNIQUE(user_id, achievement_id) is the backstop under the service check."""
    from sqlalchemy.exc import IntegrityError
    import pytest

    user = db_session.scalar(select(User))
    achievement = db_session.scalar(select(Achievement))

    for _ in range(2):
        db_session.add(
            UserAchievement(user_id=user.id, achievement_id=achievement.id)
        )

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_xp_and_streak_achievements_unlock_at_their_thresholds(
    db_session: Session,
) -> None:
    user = db_session.scalar(select(User))
    stats = db_session.get(UserStats, user.id)
    stats.total_xp = 99
    stats.current_streak = 2
    db_session.commit()

    keys = {a.key for a in achievement_service.evaluate(db_session, user)}
    assert "XP_100" not in keys
    assert "STREAK_3" not in keys

    stats.total_xp = 100
    stats.current_streak = 3
    db_session.commit()

    keys = {a.key for a in achievement_service.evaluate(db_session, user)}
    db_session.commit()
    assert "XP_100" in keys
    assert "STREAK_3" in keys
    assert "STREAK_7" not in keys


def test_a_rolled_back_completion_takes_its_achievements_with_it(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    """Achievements share the completion transaction, so they cannot survive a
    rollback of the completion that earned them."""
    from app.repositories import progress_repo
    from tests.test_api_lessons import answer_all_correctly, complete, first_lesson, start
    import pytest

    lesson = first_lesson(db_session)
    attempt = start(client, lesson.id)["attempt_id"]
    answer_all_correctly(client, db_session, lesson, attempt)

    def explode(*_args, **_kwargs):
        raise RuntimeError("simulated failure after achievements were staged")

    monkeypatch.setattr(progress_repo, "get_or_create_skill_progress", explode)

    with pytest.raises(RuntimeError):
        complete(client, lesson.id, attempt)

    db_session.expire_all()
    user = db_session.scalar(select(User))
    rows = db_session.scalars(
        select(UserAchievement).where(UserAchievement.user_id == user.id)
    ).all()

    assert rows == []
