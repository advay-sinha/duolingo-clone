"""API tests for the lesson engine.

Covers the happy path, every failure path, the security guarantee that canonical
answers never leave the server, idempotency, ownership, and transaction rollback.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session


def utc_today():
    """Today, on the same basis the service uses.

    The streak and daily-XP rules run on `datetime.now(timezone.utc).date()`.
    Tests originally used local `date.today()`, which agrees with UTC for most
    of the day and silently disagrees after local midnight in a timezone ahead
    of UTC -- so these tests passed for weeks and then failed overnight with no
    code change. A test must use the same clock basis as the code it checks.
    """
    return datetime.now(timezone.utc).date()


from app.models import (
    Exercise,
    ExerciseType,
    Lesson,
    LessonAttempt,
    LessonAttemptAnswer,
    Skill,
    User,
    UserSkillProgress,
    UserStats,
)

from tests.conftest import make_user

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def first_lesson(db: Session) -> Lesson:
    return db.scalars(select(Lesson).order_by(Lesson.id)).first()


def correct_payload(exercise: Exercise) -> dict[str, Any]:
    """Build a submission the grader will accept, from the canonical answer.

    Test-side only. It reads `correct_answer` straight from the database, which
    is exactly what a client cannot do — that asymmetry is the point.
    """
    answer = exercise.correct_answer
    if exercise.type is ExerciseType.MULTIPLE_CHOICE:
        return {"option_id": answer["option_id"]}
    if exercise.type is ExerciseType.TRANSLATE:
        return {"tokens": answer["accepted"][0].split()}
    if exercise.type is ExerciseType.MATCH_PAIRS:
        return {"pairs": answer["pairs"]}
    return {"text": answer["accepted"][0]}


def wrong_payload(exercise: Exercise) -> dict[str, Any]:
    """Build a submission the grader will reject."""
    if exercise.type is ExerciseType.MULTIPLE_CHOICE:
        correct = exercise.correct_answer["option_id"]
        other = next(o["id"] for o in exercise.data["options"] if o["id"] != correct)
        return {"option_id": other}
    if exercise.type is ExerciseType.TRANSLATE:
        return {"tokens": ["definitely", "wrong"]}
    if exercise.type is ExerciseType.MATCH_PAIRS:
        pairs = exercise.correct_answer["pairs"]
        # Rotate the right-hand sides so every pairing is wrong but every id is
        # still valid for this exercise.
        rights = [p[1] for p in pairs]
        return {"pairs": [[p[0], rights[(i + 1) % len(rights)]] for i, p in enumerate(pairs)]}
    return {"text": "definitely wrong"}


def start(client: TestClient, lesson_id: int) -> dict[str, Any]:
    response = client.post(f"/api/v1/lessons/{lesson_id}/start")
    assert response.status_code == 200, response.text
    return response.json()


def answer(
    client: TestClient,
    lesson_id: int,
    attempt_id: int,
    exercise: Exercise,
    payload: dict[str, Any],
):
    return client.post(
        f"/api/v1/lessons/{lesson_id}/answer",
        json={
            "attempt_id": attempt_id,
            "exercise_id": exercise.id,
            "answer": payload,
        },
    )


def answer_all_correctly(
    client: TestClient, db: Session, lesson: Lesson, attempt_id: int
) -> None:
    for exercise in lesson.exercises:
        response = answer(
            client, lesson.id, attempt_id, exercise, correct_payload(exercise)
        )
        assert response.status_code == 200, response.text
        assert response.json()["correct"] is True


def complete(client: TestClient, lesson_id: int, attempt_id: int):
    return client.post(
        f"/api/v1/lessons/{lesson_id}/complete", json={"attempt_id": attempt_id}
    )


# --------------------------------------------------------------------------
# GET /lessons/{id} — including the security guarantee
# --------------------------------------------------------------------------


def test_get_lesson_returns_its_exercises(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)

    body = client.get(f"/api/v1/lessons/{lesson.id}").json()

    assert body["id"] == lesson.id
    assert body["title"] == lesson.title
    assert body["skill"]["title"] == lesson.skill.title
    assert len(body["exercises"]) == 5
    assert {e["type"] for e in body["exercises"]} == {t.value for t in ExerciseType}


def test_get_lesson_404s_for_an_unknown_id(client: TestClient) -> None:
    response = client.get("/api/v1/lessons/999999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def _find_forbidden_keys(node: Any, path: str = "$") -> list[str]:
    """Recursively hunt for anything that looks like an answer key."""
    forbidden = {
        "correct_answer",
        "accepted_answers",
        "accepted",
        "answer_key",
        "answer",
        "solution",
        "option_id",
        "pairs",
    }
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in forbidden:
                found.append(f"{path}.{key}")
            found.extend(_find_forbidden_keys(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            found.extend(_find_forbidden_keys(item, f"{path}[{index}]"))
    return found


def test_lesson_response_never_exposes_the_answer(
    client: TestClient, db_session: Session
) -> None:
    """The security guarantee, checked recursively over the whole body.

    This test fails if anyone ever adds an answer-bearing field to a lesson
    response schema — which is the point of writing it recursively rather than
    asserting on a fixed set of keys.
    """
    lesson = first_lesson(db_session)

    body = client.get(f"/api/v1/lessons/{lesson.id}").json()

    leaks = _find_forbidden_keys(body)
    assert leaks == [], f"answer data leaked at: {leaks}"


def test_start_response_never_exposes_the_answer(
    client: TestClient, db_session: Session
) -> None:
    """`/start` embeds the lesson, so it needs the same guarantee."""
    lesson = first_lesson(db_session)

    body = start(client, lesson.id)

    assert _find_forbidden_keys(body) == []


def test_the_answer_is_in_the_database_but_not_in_the_response(
    client: TestClient, db_session: Session
) -> None:
    """Proves the omission is real, not an artefact of empty seed data."""
    lesson = first_lesson(db_session)
    exercise = lesson.exercises[0]
    assert exercise.correct_answer  # the server does have it

    body = client.get(f"/api/v1/lessons/{lesson.id}").json()
    serialised = str(body)

    assert str(exercise.correct_answer["option_id"]) not in serialised.replace(
        str(exercise.id), ""
    )


# --------------------------------------------------------------------------
# POST /lessons/{id}/start
# --------------------------------------------------------------------------


def test_start_creates_an_attempt(client: TestClient, db_session: Session) -> None:
    lesson = first_lesson(db_session)

    body = start(client, lesson.id)

    attempt = db_session.get(LessonAttempt, body["attempt_id"])
    assert attempt is not None
    assert attempt.lesson_id == lesson.id
    assert attempt.completed is False
    assert body["hearts"] == 5


def test_start_awards_nothing_and_deducts_nothing(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    user = db_session.scalar(select(User))
    before = db_session.get(UserStats, user.id)
    xp_before, hearts_before, streak_before = (
        before.total_xp,
        before.hearts,
        before.current_streak,
    )

    start(client, lesson.id)
    db_session.expire_all()

    after = db_session.get(UserStats, user.id)
    assert (after.total_xp, after.hearts, after.current_streak) == (
        xp_before,
        hearts_before,
        streak_before,
    )


def test_start_404s_for_an_unknown_lesson(client: TestClient) -> None:
    assert client.post("/api/v1/lessons/999999/start").status_code == 404


def test_start_is_refused_with_no_hearts(
    client: TestClient, db_session: Session
) -> None:
    user = db_session.scalar(select(User))
    db_session.get(UserStats, user.id).hearts = 0
    db_session.commit()

    response = client.post(f"/api/v1/lessons/{first_lesson(db_session).id}/start")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


# --------------------------------------------------------------------------
# POST /lessons/{id}/answer
# --------------------------------------------------------------------------


def test_a_correct_answer_earns_xp_and_keeps_hearts(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    attempt_id = start(client, lesson.id)["attempt_id"]
    exercise = lesson.exercises[0]

    body = answer(
        client, lesson.id, attempt_id, exercise, correct_payload(exercise)
    ).json()

    assert body["correct"] is True
    assert body["xp_earned"] == 10
    assert body["hearts_remaining"] == 5
    assert body["correct_answer"] is None  # not revealed when correct
    assert body["answered_count"] == 1
    assert body["total_exercises"] == 5


def test_a_wrong_answer_costs_a_heart_and_reveals_the_answer(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    attempt_id = start(client, lesson.id)["attempt_id"]
    exercise = lesson.exercises[0]

    body = answer(
        client, lesson.id, attempt_id, exercise, wrong_payload(exercise)
    ).json()

    assert body["correct"] is False
    assert body["xp_earned"] == 0
    assert body["hearts_remaining"] == 4
    # Revealed only after a graded submission -- a heart has already been spent.
    assert body["correct_answer"]


def test_all_five_exercise_types_can_be_answered_over_http(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    attempt_id = start(client, lesson.id)["attempt_id"]

    for exercise in lesson.exercises:
        response = answer(
            client, lesson.id, attempt_id, exercise, correct_payload(exercise)
        )
        assert response.status_code == 200, f"{exercise.type}: {response.text}"
        assert response.json()["correct"] is True, exercise.type


def test_a_malformed_payload_is_422_and_costs_no_heart(
    client: TestClient, db_session: Session
) -> None:
    """A client bug must not be charged to the learner."""
    lesson = first_lesson(db_session)
    attempt_id = start(client, lesson.id)["attempt_id"]
    exercise = lesson.exercises[0]

    response = answer(client, lesson.id, attempt_id, exercise, {"nonsense": True})

    assert response.status_code == 422
    db_session.expire_all()
    user = db_session.scalar(select(User))
    assert db_session.get(UserStats, user.id).hearts == 5


def test_answering_an_unknown_attempt_is_404(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    response = answer(client, lesson.id, 999999, lesson.exercises[0], {"text": "x"})
    assert response.status_code == 404


def test_answering_an_exercise_from_another_lesson_is_404(
    client: TestClient, db_session: Session
) -> None:
    """Cross-lesson submission must be impossible."""
    lessons = db_session.scalars(select(Lesson).order_by(Lesson.id)).all()
    lesson, other = lessons[0], lessons[1]
    attempt_id = start(client, lesson.id)["attempt_id"]

    response = answer(
        client, lesson.id, attempt_id, other.exercises[0], {"text": "x"}
    )

    assert response.status_code == 404


def test_using_an_attempt_from_another_lesson_is_404(
    client: TestClient, db_session: Session
) -> None:
    lessons = db_session.scalars(select(Lesson).order_by(Lesson.id)).all()
    lesson, other = lessons[0], lessons[1]
    attempt_id = start(client, other.id)["attempt_id"]

    response = answer(
        client, lesson.id, attempt_id, lesson.exercises[0], {"text": "x"}
    )

    assert response.status_code == 404


def test_a_user_cannot_answer_another_users_attempt(
    client: TestClient, db_session: Session
) -> None:
    """Ownership is enforced server-side from the dependency, never the body."""
    lesson = first_lesson(db_session)

    intruder = make_user(username="intruder", display_name="Someone Else")
    db_session.add(intruder)
    db_session.flush()
    foreign_attempt = LessonAttempt(user_id=intruder.id, lesson_id=lesson.id)
    db_session.add(foreign_attempt)
    db_session.commit()

    response = answer(
        client, lesson.id, foreign_attempt.id, lesson.exercises[0], {"text": "x"}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_answers_are_rejected_once_hearts_reach_zero(
    client: TestClient, db_session: Session
) -> None:
    """The failure path: five wrong answers drain the hearts, then it stops."""
    lesson = first_lesson(db_session)
    attempt_id = start(client, lesson.id)["attempt_id"]

    hearts_seen = []
    for exercise in lesson.exercises:
        response = answer(
            client, lesson.id, attempt_id, exercise, wrong_payload(exercise)
        )
        assert response.status_code == 200, response.text
        hearts_seen.append(response.json()["hearts_remaining"])

    assert hearts_seen == [4, 3, 2, 1, 0]

    # A sixth answer, in a new attempt, is refused.
    second = client.post(f"/api/v1/lessons/{lesson.id}/start")
    assert second.status_code == 409

    db_session.expire_all()
    user = db_session.scalar(select(User))
    assert db_session.get(UserStats, user.id).hearts == 0


def test_partial_progress_survives_running_out_of_hearts(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    attempt_id = start(client, lesson.id)["attempt_id"]

    answer(client, lesson.id, attempt_id, lesson.exercises[0], correct_payload(lesson.exercises[0]))
    for exercise in lesson.exercises[1:]:
        answer(client, lesson.id, attempt_id, exercise, wrong_payload(exercise))

    db_session.expire_all()
    attempt = db_session.get(LessonAttempt, attempt_id)
    assert attempt.correct_answers == 1
    assert attempt.incorrect_answers == 4
    assert attempt.completed is False
    assert len(attempt.answers) == 5


# --------------------------------------------------------------------------
# Idempotency
# --------------------------------------------------------------------------


def test_resubmitting_the_same_answer_does_not_charge_twice(
    client: TestClient, db_session: Session
) -> None:
    """The mandatory idempotency test, for a wrong answer (the costly case)."""
    lesson = first_lesson(db_session)
    attempt_id = start(client, lesson.id)["attempt_id"]
    exercise = lesson.exercises[0]

    first = answer(
        client, lesson.id, attempt_id, exercise, wrong_payload(exercise)
    ).json()
    second = answer(
        client, lesson.id, attempt_id, exercise, wrong_payload(exercise)
    ).json()

    assert first["hearts_remaining"] == 4
    assert first["already_answered"] is False
    # The replay returns the original verdict rather than a conflict, so a
    # retried request after a dropped response is harmless.
    assert second["already_answered"] is True
    assert second["correct"] is first["correct"]
    assert second["hearts_remaining"] == 4  # not 3

    db_session.expire_all()
    rows = db_session.scalars(
        select(LessonAttemptAnswer).where(
            LessonAttemptAnswer.attempt_id == attempt_id
        )
    ).all()
    assert len(rows) == 1


def test_a_resubmission_cannot_change_a_wrong_answer_to_right(
    client: TestClient, db_session: Session
) -> None:
    """No second bite: the first verdict stands."""
    lesson = first_lesson(db_session)
    attempt_id = start(client, lesson.id)["attempt_id"]
    exercise = lesson.exercises[0]

    answer(client, lesson.id, attempt_id, exercise, wrong_payload(exercise))
    retry = answer(
        client, lesson.id, attempt_id, exercise, correct_payload(exercise)
    ).json()

    assert retry["correct"] is False
    assert retry["already_answered"] is True
    assert retry["xp_earned"] == 0


def test_resubmitting_a_correct_answer_does_not_double_xp(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    attempt_id = start(client, lesson.id)["attempt_id"]
    exercise = lesson.exercises[0]

    answer(client, lesson.id, attempt_id, exercise, correct_payload(exercise))
    answer(client, lesson.id, attempt_id, exercise, correct_payload(exercise))

    db_session.expire_all()
    attempt = db_session.get(LessonAttempt, attempt_id)
    assert attempt.correct_answers == 1
    assert sum(a.xp_earned for a in attempt.answers) == 10


def test_the_database_constraint_blocks_a_duplicate_answer_row(
    db_session: Session,
) -> None:
    """The guarantee under the service check: UNIQUE(attempt_id, exercise_id)."""
    from sqlalchemy.exc import IntegrityError

    lesson = first_lesson(db_session)
    user = db_session.scalar(select(User))
    attempt = LessonAttempt(user_id=user.id, lesson_id=lesson.id)
    db_session.add(attempt)
    db_session.flush()

    for _ in range(2):
        db_session.add(
            LessonAttemptAnswer(
                attempt_id=attempt.id,
                exercise_id=lesson.exercises[0].id,
                submitted={},
                is_correct=True,
            )
        )

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


# --------------------------------------------------------------------------
# POST /lessons/{id}/complete
# --------------------------------------------------------------------------


def test_completing_a_perfect_lesson_awards_everything(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    attempt_id = start(client, lesson.id)["attempt_id"]
    answer_all_correctly(client, db_session, lesson, attempt_id)

    body = complete(client, lesson.id, attempt_id).json()

    # 5 correct x 10 XP + 10 completion bonus
    assert body["xp_earned"] == 60
    assert body["correct_answers"] == 5
    assert body["incorrect_answers"] == 0
    assert body["accuracy"] == 1.0
    assert body["first_completion"] is True
    assert body["total_xp"] == 60
    assert body["daily_xp"] == 60
    assert body["current_streak"] == 1
    assert body["streak_extended"] is True
    assert body["lessons_completed"] == 1
    assert body["total_lessons"] == 2
    assert body["crowns"] == 0  # one of two lessons done
    assert body["crown_earned"] is False


def test_completion_persists_to_every_table(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    user = db_session.scalar(select(User))
    attempt_id = start(client, lesson.id)["attempt_id"]
    answer_all_correctly(client, db_session, lesson, attempt_id)
    complete(client, lesson.id, attempt_id)

    db_session.expire_all()

    attempt = db_session.get(LessonAttempt, attempt_id)
    assert attempt.completed is True
    assert attempt.completed_at is not None
    assert attempt.xp_earned == 60

    stats = db_session.get(UserStats, user.id)
    assert stats.total_xp == 60
    assert stats.last_activity_date == utc_today()

    progress = db_session.scalar(
        select(UserSkillProgress).where(
            UserSkillProgress.user_id == user.id,
            UserSkillProgress.skill_id == lesson.skill_id,
        )
    )
    assert progress.lessons_completed == 1
    assert progress.xp_earned == 60


def test_finishing_every_lesson_in_a_skill_awards_a_crown(
    client: TestClient, db_session: Session
) -> None:
    skill = db_session.scalars(select(Skill).order_by(Skill.id)).first()

    for index, lesson in enumerate(skill.lessons):
        attempt_id = start(client, lesson.id)["attempt_id"]
        answer_all_correctly(client, db_session, lesson, attempt_id)
        body = complete(client, lesson.id, attempt_id).json()

    assert body["lessons_completed"] == 2
    assert body["total_lessons"] == 2
    assert body["crowns"] == 1
    assert body["crown_earned"] is True


def test_a_crown_unlocks_the_next_skill_on_the_path(
    client: TestClient, db_session: Session
) -> None:
    """End-to-end: the lesson engine drives the Phase 3 unlock rule."""
    skill = db_session.scalars(select(Skill).order_by(Skill.id)).first()

    for lesson in skill.lessons:
        attempt_id = start(client, lesson.id)["attempt_id"]
        answer_all_correctly(client, db_session, lesson, attempt_id)
        complete(client, lesson.id, attempt_id)

    path = client.get("/api/v1/courses/1/path").json()
    states = [s["state"] for u in path["units"] for s in u["skills"]]

    assert states[0] == "COMPLETED"
    assert states[1] == "AVAILABLE"
    assert states[2] == "LOCKED"


def test_completion_with_mistakes_awards_only_correct_answer_xp(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    attempt_id = start(client, lesson.id)["attempt_id"]

    answer(client, lesson.id, attempt_id, lesson.exercises[0], wrong_payload(lesson.exercises[0]))
    for exercise in lesson.exercises[1:]:
        answer(client, lesson.id, attempt_id, exercise, correct_payload(exercise))

    body = complete(client, lesson.id, attempt_id).json()

    assert body["correct_answers"] == 4
    assert body["incorrect_answers"] == 1
    assert body["xp_earned"] == 50  # 4 x 10 + 10 bonus
    assert body["accuracy"] == 0.8
    assert body["hearts_remaining"] == 4


def test_completing_twice_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    """Idempotent completion: the second call gets a conflict, not more XP."""
    lesson = first_lesson(db_session)
    attempt_id = start(client, lesson.id)["attempt_id"]
    answer_all_correctly(client, db_session, lesson, attempt_id)

    assert complete(client, lesson.id, attempt_id).status_code == 200
    second = complete(client, lesson.id, attempt_id)

    assert second.status_code == 409

    db_session.expire_all()
    user = db_session.scalar(select(User))
    assert db_session.get(UserStats, user.id).total_xp == 60  # not 120


def test_replaying_a_lesson_awards_no_further_xp(
    client: TestClient, db_session: Session
) -> None:
    """Repeat practice is allowed but cannot farm unlimited XP."""
    lesson = first_lesson(db_session)

    first_attempt = start(client, lesson.id)["attempt_id"]
    answer_all_correctly(client, db_session, lesson, first_attempt)
    complete(client, lesson.id, first_attempt)

    second_attempt = start(client, lesson.id)["attempt_id"]
    answer_all_correctly(client, db_session, lesson, second_attempt)
    body = complete(client, lesson.id, second_attempt).json()

    assert body["first_completion"] is False
    assert body["xp_earned"] == 0
    assert body["total_xp"] == 60
    assert body["lessons_completed"] == 1  # not double counted


def test_completing_an_unfinished_lesson_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    attempt_id = start(client, lesson.id)["attempt_id"]
    exercise = lesson.exercises[0]
    answer(client, lesson.id, attempt_id, exercise, correct_payload(exercise))

    response = complete(client, lesson.id, attempt_id)

    assert response.status_code == 409
    assert "1 of 5" in response.json()["error"]["message"]


def test_completing_without_answering_anything_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    attempt_id = start(client, lesson.id)["attempt_id"]

    assert complete(client, lesson.id, attempt_id).status_code == 409


def test_completing_an_unknown_attempt_is_404(
    client: TestClient, db_session: Session
) -> None:
    assert complete(client, first_lesson(db_session).id, 999999).status_code == 404


def test_a_user_cannot_complete_another_users_attempt(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    intruder = make_user(username="intruder2", display_name="Someone Else")
    db_session.add(intruder)
    db_session.flush()
    foreign = LessonAttempt(user_id=intruder.id, lesson_id=lesson.id)
    db_session.add(foreign)
    db_session.commit()

    assert complete(client, lesson.id, foreign.id).status_code == 403


def test_answering_after_completion_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    attempt_id = start(client, lesson.id)["attempt_id"]
    answer_all_correctly(client, db_session, lesson, attempt_id)
    complete(client, lesson.id, attempt_id)

    response = answer(
        client, lesson.id, attempt_id, lesson.exercises[0], {"text": "x"}
    )

    assert response.status_code == 409


# --------------------------------------------------------------------------
# Streak behaviour through the API
# --------------------------------------------------------------------------


def test_a_second_lesson_the_same_day_does_not_extend_the_streak(
    client: TestClient, db_session: Session
) -> None:
    skill = db_session.scalars(select(Skill).order_by(Skill.id)).first()

    bodies = []
    for lesson in skill.lessons:
        attempt_id = start(client, lesson.id)["attempt_id"]
        answer_all_correctly(client, db_session, lesson, attempt_id)
        bodies.append(complete(client, lesson.id, attempt_id).json())

    assert bodies[0]["current_streak"] == 1
    assert bodies[0]["streak_extended"] is True
    assert bodies[1]["current_streak"] == 1
    assert bodies[1]["streak_extended"] is False


def test_completing_the_day_after_extends_the_streak(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    user = db_session.scalar(select(User))

    # Pretend the learner practised yesterday.
    stats = db_session.get(UserStats, user.id)
    stats.current_streak = 3
    stats.longest_streak = 3
    stats.last_activity_date = utc_today() - timedelta(days=1)
    db_session.commit()

    attempt_id = start(client, lesson.id)["attempt_id"]
    answer_all_correctly(client, db_session, lesson, attempt_id)
    body = complete(client, lesson.id, attempt_id).json()

    assert body["current_streak"] == 4
    assert body["longest_streak"] == 4


def test_a_missed_day_resets_the_streak_but_keeps_the_record(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    user = db_session.scalar(select(User))

    stats = db_session.get(UserStats, user.id)
    stats.current_streak = 12
    stats.longest_streak = 12
    stats.last_activity_date = utc_today() - timedelta(days=5)
    db_session.commit()

    attempt_id = start(client, lesson.id)["attempt_id"]
    answer_all_correctly(client, db_session, lesson, attempt_id)
    body = complete(client, lesson.id, attempt_id).json()

    assert body["current_streak"] == 1
    assert body["longest_streak"] == 12


def test_daily_xp_rolls_over_to_a_new_day(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    user = db_session.scalar(select(User))

    stats = db_session.get(UserStats, user.id)
    stats.daily_xp = 200
    stats.last_activity_date = utc_today() - timedelta(days=1)
    db_session.commit()

    attempt_id = start(client, lesson.id)["attempt_id"]
    answer_all_correctly(client, db_session, lesson, attempt_id)
    body = complete(client, lesson.id, attempt_id).json()

    assert body["daily_xp"] == 60  # yesterday's 200 is not carried forward


# --------------------------------------------------------------------------
# Transaction rollback
# --------------------------------------------------------------------------


def test_a_failure_during_completion_rolls_back_every_write(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    """Force an error mid-transaction and prove nothing persisted.

    The failure is injected at the *last* write of the completion transaction —
    the skill-progress update — so XP, streak and the attempt flag have all
    already been set on their objects. If the transaction were not atomic, the
    learner would end up with XP for a lesson their path still showed as
    unfinished, and nothing would ever repair it.

    Not mocked away: the rollback is verified against the real test database.
    """
    from app.repositories import progress_repo

    lesson = first_lesson(db_session)
    user = db_session.scalar(select(User))
    attempt_id = start(client, lesson.id)["attempt_id"]
    answer_all_correctly(client, db_session, lesson, attempt_id)

    def explode(*_args, **_kwargs):
        raise RuntimeError("simulated failure during skill progress update")

    monkeypatch.setattr(progress_repo, "get_or_create_skill_progress", explode)

    with pytest.raises(RuntimeError):
        complete(client, lesson.id, attempt_id)

    db_session.expire_all()

    # Nothing from the completion survived.
    stats = db_session.get(UserStats, user.id)
    assert stats.total_xp == 0
    assert stats.current_streak == 0
    assert stats.last_activity_date is None

    attempt = db_session.get(LessonAttempt, attempt_id)
    assert attempt.completed is False
    assert attempt.completed_at is None

    progress = db_session.scalar(
        select(UserSkillProgress).where(
            UserSkillProgress.user_id == user.id,
            UserSkillProgress.skill_id == lesson.skill_id,
        )
    )
    assert progress.lessons_completed == 0
    assert progress.crowns == 0

    # The answers, committed by earlier requests, are untouched -- they belong to
    # a different transaction.
    assert len(attempt.answers) == 5


def test_the_lesson_can_still_be_completed_after_a_rolled_back_attempt(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    """A failed transaction leaves the system usable, not wedged."""
    from app.repositories import progress_repo

    lesson = first_lesson(db_session)
    attempt_id = start(client, lesson.id)["attempt_id"]
    answer_all_correctly(client, db_session, lesson, attempt_id)

    original = progress_repo.get_or_create_skill_progress

    def explode_once(*args, **kwargs):
        monkeypatch.setattr(progress_repo, "get_or_create_skill_progress", original)
        raise RuntimeError("simulated transient failure")

    monkeypatch.setattr(progress_repo, "get_or_create_skill_progress", explode_once)

    with pytest.raises(RuntimeError):
        complete(client, lesson.id, attempt_id)

    body = complete(client, lesson.id, attempt_id).json()

    assert body["xp_earned"] == 60
    assert body["total_xp"] == 60
