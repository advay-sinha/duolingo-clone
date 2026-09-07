"""Two learners, one database, no leakage.

**This is the file Phase 9 exists to make passable.** Everything else in the
phase — password hashing, cookies, the session table — is machinery in service of
one property: what Alice does must not show up for Bob.

The tests are written as two logged-in clients sharing one database, which is
exactly the production shape. Nothing here calls a service directly; if isolation
broke at the route or dependency layer, a service-level test would still pass.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Exercise, Lesson, LessonAttempt, User


def _correct_payload(exercise: Exercise) -> dict:
    answer = exercise.correct_answer
    if exercise.type.value == "MULTIPLE_CHOICE":
        return {"option_id": answer["option_id"]}
    if exercise.type.value == "TRANSLATE":
        return {"tokens": answer["accepted"][0].split()}
    if exercise.type.value == "MATCH_PAIRS":
        return {"pairs": [list(pair) for pair in answer["pairs"]]}
    return {"text": answer["accepted"][0]}


def _complete_first_lesson(client: TestClient, db: Session) -> dict:
    """Play lesson 1 perfectly and return the completion body."""
    lesson = db.scalars(select(Lesson).order_by(Lesson.id)).first()
    start = client.post(f"/api/v1/lessons/{lesson.id}/start").json()

    for exercise in lesson.exercises:
        response = client.post(
            f"/api/v1/lessons/{lesson.id}/answer",
            json={
                "attempt_id": start["attempt_id"],
                "exercise_id": exercise.id,
                "answer": _correct_payload(exercise),
            },
        )
        assert response.status_code == 200, response.text

    done = client.post(
        f"/api/v1/lessons/{lesson.id}/complete",
        json={"attempt_id": start["attempt_id"]},
    )
    assert done.status_code == 200, done.text
    return done.json()


# --------------------------------------------------------------------------
# Progress isolation
# --------------------------------------------------------------------------


def test_one_learners_xp_does_not_appear_for_another(
    register_user, db_session: Session
) -> None:
    alice = register_user("alice@example.com", display_name="Alice")
    bob = register_user("bob@example.com", display_name="Bob")

    result = _complete_first_lesson(alice, db_session)
    assert result["total_xp"] == 60

    assert alice.get("/api/v1/users/me/stats").json()["total_xp"] == 60
    assert bob.get("/api/v1/users/me/stats").json()["total_xp"] == 0


def test_a_second_learner_starts_with_a_clean_slate(
    register_user, db_session: Session
) -> None:
    alice = register_user("alice@example.com", display_name="Alice")
    _complete_first_lesson(alice, db_session)

    bob = register_user("bob@example.com", display_name="Bob")
    stats = bob.get("/api/v1/users/me/stats").json()

    assert stats["total_xp"] == 0
    assert stats["hearts"] == 5
    assert stats["current_streak"] == 0
    assert stats["daily_xp"] == 0


def test_skill_progress_is_per_learner(register_user, db_session: Session) -> None:
    alice = register_user("alice@example.com", display_name="Alice")
    bob = register_user("bob@example.com", display_name="Bob")

    _complete_first_lesson(alice, db_session)

    def first_skill(client: TestClient) -> dict:
        path = client.get("/api/v1/courses/1/path").json()
        return path["units"][0]["skills"][0]

    assert first_skill(alice)["lessons_completed"] == 1
    assert first_skill(bob)["lessons_completed"] == 0


def test_achievements_are_per_learner(register_user, db_session: Session) -> None:
    alice = register_user("alice@example.com", display_name="Alice")
    bob = register_user("bob@example.com", display_name="Bob")

    result = _complete_first_lesson(alice, db_session)
    assert result["achievements_unlocked"]  # Alice earned at least one

    def unlocked(client: TestClient) -> set[str]:
        body = client.get("/api/v1/users/me/achievements").json()
        return {a["key"] for a in body["achievements"] if a["unlocked"]}

    assert unlocked(alice)
    assert unlocked(bob) == set()


def test_hearts_are_per_learner(register_user, db_session: Session) -> None:
    alice = register_user("alice@example.com", display_name="Alice")
    bob = register_user("bob@example.com", display_name="Bob")

    lesson = db_session.scalars(select(Lesson).order_by(Lesson.id)).first()
    start = alice.post(f"/api/v1/lessons/{lesson.id}/start").json()
    exercise = next(e for e in lesson.exercises if e.type.value == "TYPE_ANSWER")
    alice.post(
        f"/api/v1/lessons/{lesson.id}/answer",
        json={
            "attempt_id": start["attempt_id"],
            "exercise_id": exercise.id,
            "answer": {"text": "definitely-wrong"},
        },
    )

    assert alice.get("/api/v1/users/me/stats").json()["hearts"] == 4
    assert bob.get("/api/v1/users/me/stats").json()["hearts"] == 5


def test_the_profile_describes_the_caller_not_the_seeded_learner(
    register_user, db_session: Session
) -> None:
    alice = register_user("alice@example.com", display_name="Alice")

    profile = alice.get("/api/v1/users/me/profile").json()

    assert profile["user"]["display_name"] == "Alice"
    assert profile["stats"]["total_xp"] == 0


# --------------------------------------------------------------------------
# Cross-user access
# --------------------------------------------------------------------------


def test_a_learner_cannot_answer_into_another_learners_attempt(
    register_user, db_session: Session
) -> None:
    """The attempt id is a number; guessing it must not be enough."""
    alice = register_user("alice@example.com", display_name="Alice")
    bob = register_user("bob@example.com", display_name="Bob")

    lesson = db_session.scalars(select(Lesson).order_by(Lesson.id)).first()
    start = alice.post(f"/api/v1/lessons/{lesson.id}/start").json()
    exercise = lesson.exercises[0]

    response = bob.post(
        f"/api/v1/lessons/{lesson.id}/answer",
        json={
            "attempt_id": start["attempt_id"],
            "exercise_id": exercise.id,
            "answer": _correct_payload(exercise),
        },
    )

    assert response.status_code == 403


def test_a_learner_cannot_complete_another_learners_attempt(
    register_user, db_session: Session
) -> None:
    alice = register_user("alice@example.com", display_name="Alice")
    bob = register_user("bob@example.com", display_name="Bob")

    lesson = db_session.scalars(select(Lesson).order_by(Lesson.id)).first()
    start = alice.post(f"/api/v1/lessons/{lesson.id}/start").json()

    response = bob.post(
        f"/api/v1/lessons/{lesson.id}/complete",
        json={"attempt_id": start["attempt_id"]},
    )

    assert response.status_code == 403


def test_a_learner_cannot_submit_a_pair_into_another_learners_attempt(
    register_user, db_session: Session
) -> None:
    """The Phase 9 endpoint must not be a weaker door than the Phase 4 one."""
    alice = register_user("alice@example.com", display_name="Alice")
    bob = register_user("bob@example.com", display_name="Bob")

    lesson = db_session.scalars(select(Lesson).order_by(Lesson.id)).first()
    start = alice.post(f"/api/v1/lessons/{lesson.id}/start").json()
    exercise = next(e for e in lesson.exercises if e.type.value == "MATCH_PAIRS")
    left, right = exercise.correct_answer["pairs"][0]

    response = bob.post(
        f"/api/v1/lessons/{lesson.id}/pair",
        json={
            "attempt_id": start["attempt_id"],
            "exercise_id": exercise.id,
            "left_id": left,
            "right_id": right,
        },
    )

    assert response.status_code == 403


def test_identity_comes_from_the_session_not_the_request(
    register_user, db_session: Session
) -> None:
    """There is no field in which to claim to be someone else.

    A body carrying `user_id` is ignored rather than honoured — the request model
    has no such field, so it cannot reach any service.
    """
    alice = register_user("alice@example.com", display_name="Alice")
    bob = register_user("bob@example.com", display_name="Bob")
    bob_id = bob.get("/api/v1/auth/me").json()["user"]["id"]

    lesson = db_session.scalars(select(Lesson).order_by(Lesson.id)).first()
    start = alice.post(
        f"/api/v1/lessons/{lesson.id}/start", json={"user_id": bob_id}
    ).json()

    attempt = db_session.get(LessonAttempt, start["attempt_id"])
    alice_id = alice.get("/api/v1/auth/me").json()["user"]["id"]
    assert attempt.user_id == alice_id


# --------------------------------------------------------------------------
# Leaderboard
# --------------------------------------------------------------------------


def test_the_leaderboard_contains_every_registered_learner(
    register_user, db_session: Session
) -> None:
    alice = register_user("alice@example.com", display_name="Alice")
    register_user("bob@example.com", display_name="Bob")

    names = {e["display_name"] for e in alice.get("/api/v1/leaderboard").json()["entries"]}

    # The seeded learner plus the two registrations. Nothing is fabricated and
    # nothing is hidden.
    assert {"Alice", "Bob"} <= names
    assert len(names) == 3


def test_the_leaderboard_orders_real_learners_by_xp(
    register_user, db_session: Session
) -> None:
    alice = register_user("alice@example.com", display_name="Alice")
    bob = register_user("bob@example.com", display_name="Bob")

    _complete_first_lesson(alice, db_session)

    entries = bob.get("/api/v1/leaderboard").json()["entries"]

    assert entries[0]["display_name"] == "Alice"
    assert entries[0]["xp"] == 60
    assert entries[0]["rank"] == 1


def test_each_learner_sees_themselves_flagged(
    register_user, db_session: Session
) -> None:
    alice = register_user("alice@example.com", display_name="Alice")
    bob = register_user("bob@example.com", display_name="Bob")

    def flagged(client: TestClient) -> str:
        entries = client.get("/api/v1/leaderboard").json()["entries"]
        return next(e["display_name"] for e in entries if e["is_current_user"])

    assert flagged(alice) == "Alice"
    assert flagged(bob) == "Bob"


def test_the_leaderboard_exposes_no_private_data(
    register_user, db_session: Session
) -> None:
    """One learner's row is shown to another, so this is the schema that matters.

    Checked against the raw response text, not the parsed fields, so a nested
    object added later cannot smuggle an address through.
    """
    alice = register_user("alice@example.com", display_name="Alice")
    register_user("bob@example.com", display_name="Bob")

    response = alice.get("/api/v1/leaderboard")
    body = response.json()

    assert "alice@example.com" not in response.text
    assert "bob@example.com" not in response.text
    assert "$2b$" not in response.text
    for entry in body["entries"]:
        assert set(entry) == {
            "rank",
            "user_id",
            "display_name",
            "avatar_url",
            "xp",
            "current_streak",
            "is_current_user",
        }


def test_no_endpoint_leaks_another_learners_email(
    register_user, db_session: Session
) -> None:
    """`/auth/me` may show your own address. Nothing else may show anyone's."""
    alice = register_user("alice@example.com", display_name="Alice")
    register_user("bob@example.com", display_name="Bob")

    for path in (
        "/api/v1/leaderboard",
        "/api/v1/users/me",
        "/api/v1/users/me/stats",
        "/api/v1/users/me/profile",
        "/api/v1/users/me/achievements",
        "/api/v1/courses/1/path",
    ):
        text = alice.get(path).text
        assert "bob@example.com" not in text, path
        assert "$2b$" not in text, path


def test_no_response_anywhere_contains_a_password_hash(
    register_user, db_session: Session
) -> None:
    alice = register_user("alice@example.com", display_name="Alice")
    hashes = db_session.scalars(select(User.password_hash)).all()

    for path in (
        "/api/v1/auth/me",
        "/api/v1/leaderboard",
        "/api/v1/users/me/profile",
    ):
        text = alice.get(path).text
        for stored in hashes:
            assert stored not in text, path
        json.loads(text)  # still valid JSON, i.e. the request actually worked
