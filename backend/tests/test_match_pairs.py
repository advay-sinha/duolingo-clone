"""Incremental match-pairs grading, and the heart rules that come with it.

The rules under test are stated in full at the top of
``services/answer_service.py``. This file is the executable version of that
comment: every numbered rule there has at least one test here.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Exercise,
    ExerciseType,
    Lesson,
    LessonAttemptAnswer,
    LessonAttemptPair,
)


def match_exercise(db: Session, lesson: Lesson) -> Exercise:
    return next(e for e in lesson.exercises if e.type is ExerciseType.MATCH_PAIRS)


def first_lesson(db: Session) -> Lesson:
    return db.scalars(select(Lesson).order_by(Lesson.id)).first()


def start(client: TestClient, lesson_id: int) -> int:
    response = client.post(f"/api/v1/lessons/{lesson_id}/start")
    assert response.status_code == 200, response.text
    return response.json()["attempt_id"]


def send_pair(
    client: TestClient, lesson_id: int, attempt_id: int, exercise_id: int, left, right
):
    return client.post(
        f"/api/v1/lessons/{lesson_id}/pair",
        json={
            "attempt_id": attempt_id,
            "exercise_id": exercise_id,
            "left_id": left,
            "right_id": right,
        },
    )


def wrong_pair(exercise: Exercise) -> tuple[str, str]:
    """A left/right combination that is on the exercise but is not a match."""
    expected = {(left, right) for left, right in exercise.correct_answer["pairs"]}
    for left in exercise.data["left"]:
        for right in exercise.data["right"]:
            if (left["id"], right["id"]) not in expected:
                return left["id"], right["id"]
    raise AssertionError("every combination is correct, which cannot happen")


def hearts(client: TestClient) -> int:
    return client.get("/api/v1/users/me/stats").json()["hearts"]


# --------------------------------------------------------------------------
# Immediate grading
# --------------------------------------------------------------------------


def test_a_correct_pair_is_accepted_immediately(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    exercise = match_exercise(db_session, lesson)
    attempt = start(client, lesson.id)
    left, right = exercise.correct_answer["pairs"][0]

    body = send_pair(client, lesson.id, attempt, exercise.id, left, right).json()

    assert body["correct"] is True
    assert body["pair_completed"] is True
    assert body["matched_pairs"] == [[left, right]]
    assert body["exercise_complete"] is False


def test_a_correct_pair_costs_no_heart(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    exercise = match_exercise(db_session, lesson)
    attempt = start(client, lesson.id)
    left, right = exercise.correct_answer["pairs"][0]

    body = send_pair(client, lesson.id, attempt, exercise.id, left, right).json()

    assert body["hearts_remaining"] == 5
    assert hearts(client) == 5


def test_a_wrong_pair_is_rejected_immediately_and_costs_one_heart(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    exercise = match_exercise(db_session, lesson)
    attempt = start(client, lesson.id)
    left, right = wrong_pair(exercise)

    body = send_pair(client, lesson.id, attempt, exercise.id, left, right).json()

    assert body["correct"] is False
    assert body["pair_completed"] is False
    assert body["hearts_remaining"] == 4
    # A wrong pair is not progress.
    assert body["matched_pairs"] == []
    assert hearts(client) == 4


def test_a_wrong_pair_does_not_reveal_the_right_one(
    client: TestClient, db_session: Session
) -> None:
    """The learner is told "no", not "no, it was r3"."""
    lesson = first_lesson(db_session)
    exercise = match_exercise(db_session, lesson)
    attempt = start(client, lesson.id)
    left, right = wrong_pair(exercise)

    response = send_pair(client, lesson.id, attempt, exercise.id, left, right)

    correct_right = dict(exercise.correct_answer["pairs"])[left]
    assert correct_right not in response.text


# --------------------------------------------------------------------------
# Idempotency and the heart rules
# --------------------------------------------------------------------------


def test_repeating_the_same_wrong_pair_costs_nothing(
    client: TestClient, db_session: Session
) -> None:
    """Rule 2. A double-click or a retried request must not charge twice."""
    lesson = first_lesson(db_session)
    exercise = match_exercise(db_session, lesson)
    attempt = start(client, lesson.id)
    left, right = wrong_pair(exercise)

    send_pair(client, lesson.id, attempt, exercise.id, left, right)
    second = send_pair(client, lesson.id, attempt, exercise.id, left, right).json()

    assert second["already_answered"] is True
    assert second["correct"] is False
    assert second["hearts_remaining"] == 4
    assert hearts(client) == 4


def test_a_different_wrong_pair_costs_its_own_heart(
    client: TestClient, db_session: Session
) -> None:
    """Rule 3. Two genuine guesses are two mistakes."""
    lesson = first_lesson(db_session)
    exercise = match_exercise(db_session, lesson)
    attempt = start(client, lesson.id)

    expected = {(left, right) for left, right in exercise.correct_answer["pairs"]}
    wrongs = [
        (left["id"], right["id"])
        for left in exercise.data["left"]
        for right in exercise.data["right"]
        if (left["id"], right["id"]) not in expected
    ][:2]

    for left, right in wrongs:
        send_pair(client, lesson.id, attempt, exercise.id, left, right)

    assert hearts(client) == 3


def test_repeating_a_correct_pair_is_idempotent(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    exercise = match_exercise(db_session, lesson)
    attempt = start(client, lesson.id)
    left, right = exercise.correct_answer["pairs"][0]

    send_pair(client, lesson.id, attempt, exercise.id, left, right)
    second = send_pair(client, lesson.id, attempt, exercise.id, left, right).json()

    assert second["already_answered"] is True
    assert second["matched_pairs"] == [[left, right]]
    rows = db_session.scalars(
        select(LessonAttemptPair).where(LessonAttemptPair.attempt_id == attempt)
    ).all()
    assert len(rows) == 1


def test_a_pair_id_that_is_not_on_the_exercise_is_422_and_costs_nothing(
    client: TestClient, db_session: Session
) -> None:
    """Rule 5. A client bug is not a wrong answer."""
    lesson = first_lesson(db_session)
    exercise = match_exercise(db_session, lesson)
    attempt = start(client, lesson.id)

    response = send_pair(client, lesson.id, attempt, exercise.id, "l99", "r99")

    assert response.status_code == 422
    assert hearts(client) == 5
    assert (
        db_session.scalars(
            select(LessonAttemptPair).where(LessonAttemptPair.attempt_id == attempt)
        ).all()
        == []
    )


def test_the_pair_endpoint_rejects_other_exercise_types(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    attempt = start(client, lesson.id)
    other = next(e for e in lesson.exercises if e.type is ExerciseType.TYPE_ANSWER)

    response = send_pair(client, lesson.id, attempt, other.id, "l1", "r1")

    assert response.status_code == 422
    assert hearts(client) == 5


def test_pairs_cannot_be_submitted_with_no_hearts(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    exercise = match_exercise(db_session, lesson)
    attempt = start(client, lesson.id)

    from app.models import UserStats

    stats = db_session.scalar(select(UserStats))
    stats.hearts = 0
    db_session.commit()

    left, right = exercise.correct_answer["pairs"][0]
    response = send_pair(client, lesson.id, attempt, exercise.id, left, right)

    assert response.status_code == 409


# --------------------------------------------------------------------------
# Completing the exercise
# --------------------------------------------------------------------------


def test_the_exercise_completes_only_when_every_pair_is_matched(
    client: TestClient, db_session: Session
) -> None:
    """Rule 6."""
    lesson = first_lesson(db_session)
    exercise = match_exercise(db_session, lesson)
    attempt = start(client, lesson.id)
    pairs = exercise.correct_answer["pairs"]

    for index, (left, right) in enumerate(pairs, start=1):
        body = send_pair(client, lesson.id, attempt, exercise.id, left, right).json()
        assert body["exercise_complete"] is (index == len(pairs))
        assert len(body["matched_pairs"]) == index


def test_completing_the_exercise_writes_exactly_one_answer_row(
    client: TestClient, db_session: Session
) -> None:
    """The existing engine is reused, not duplicated."""
    lesson = first_lesson(db_session)
    exercise = match_exercise(db_session, lesson)
    attempt = start(client, lesson.id)

    for left, right in exercise.correct_answer["pairs"]:
        send_pair(client, lesson.id, attempt, exercise.id, left, right)

    rows = db_session.scalars(
        select(LessonAttemptAnswer).where(
            LessonAttemptAnswer.attempt_id == attempt,
            LessonAttemptAnswer.exercise_id == exercise.id,
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].is_correct is True
    assert rows[0].xp_earned == 10


def test_a_flawless_exercise_earns_xp_and_a_flawed_one_does_not(
    client: TestClient, db_session: Session
) -> None:
    """Rule 7 — the same rule the other four exercise types follow."""
    lesson = first_lesson(db_session)
    exercise = match_exercise(db_session, lesson)
    attempt = start(client, lesson.id)

    left, right = wrong_pair(exercise)
    send_pair(client, lesson.id, attempt, exercise.id, left, right)
    for left, right in exercise.correct_answer["pairs"]:
        body = send_pair(client, lesson.id, attempt, exercise.id, left, right).json()

    assert body["exercise_complete"] is True
    assert body["xp_earned"] == 0

    row = db_session.scalar(
        select(LessonAttemptAnswer).where(
            LessonAttemptAnswer.attempt_id == attempt,
            LessonAttemptAnswer.exercise_id == exercise.id,
        )
    )
    assert row.is_correct is False
    # Hearts were charged per wrong pair; the answer row must not charge again.
    assert row.hearts_lost == 0


def test_submitting_a_pair_after_the_exercise_is_complete_changes_nothing(
    client: TestClient, db_session: Session
) -> None:
    lesson = first_lesson(db_session)
    exercise = match_exercise(db_session, lesson)
    attempt = start(client, lesson.id)
    for left, right in exercise.correct_answer["pairs"]:
        send_pair(client, lesson.id, attempt, exercise.id, left, right)

    before = hearts(client)
    left, right = exercise.correct_answer["pairs"][0]
    body = send_pair(client, lesson.id, attempt, exercise.id, left, right).json()

    assert body["already_answered"] is True
    assert hearts(client) == before
    rows = db_session.scalars(
        select(LessonAttemptAnswer).where(
            LessonAttemptAnswer.attempt_id == attempt,
            LessonAttemptAnswer.exercise_id == exercise.id,
        )
    ).all()
    assert len(rows) == 1


# --------------------------------------------------------------------------
# The whole lesson still works
# --------------------------------------------------------------------------


def test_a_lesson_played_with_incremental_pairs_completes_and_rewards_once(
    client: TestClient, db_session: Session
) -> None:
    """Part 20: exercise 1 → 2 → match pairs → 4 → 5 → complete."""
    lesson = first_lesson(db_session)
    attempt = start(client, lesson.id)

    for exercise in lesson.exercises:
        if exercise.type is ExerciseType.MATCH_PAIRS:
            for left, right in exercise.correct_answer["pairs"]:
                response = send_pair(
                    client, lesson.id, attempt, exercise.id, left, right
                )
                assert response.status_code == 200, response.text
            continue

        answer = exercise.correct_answer
        if exercise.type is ExerciseType.MULTIPLE_CHOICE:
            payload = {"option_id": answer["option_id"]}
        elif exercise.type is ExerciseType.TRANSLATE:
            payload = {"tokens": answer["accepted"][0].split()}
        else:
            payload = {"text": answer["accepted"][0]}

        response = client.post(
            f"/api/v1/lessons/{lesson.id}/answer",
            json={
                "attempt_id": attempt,
                "exercise_id": exercise.id,
                "answer": payload,
            },
        )
        assert response.status_code == 200, response.text

    done = client.post(
        f"/api/v1/lessons/{lesson.id}/complete", json={"attempt_id": attempt}
    )

    assert done.status_code == 200, done.text
    body = done.json()
    assert body["total_exercises"] == 5
    assert body["correct_answers"] == 5
    assert body["xp_earned"] == 60  # 5 x 10 + the lesson's 10 reward
    assert body["hearts_remaining"] == 5

    # And completing again cannot pay twice.
    again = client.post(
        f"/api/v1/lessons/{lesson.id}/complete", json={"attempt_id": attempt}
    )
    assert again.status_code == 409
    assert client.get("/api/v1/users/me/stats").json()["total_xp"] == 60


def test_a_lesson_cannot_be_completed_with_pairs_left_unmatched(
    client: TestClient, db_session: Session
) -> None:
    """The match-pairs exercise has no answer row until every pair is matched,
    so the lesson is not finished — which the existing completion check already
    enforces, with no new special case."""
    lesson = first_lesson(db_session)
    exercise = match_exercise(db_session, lesson)
    attempt = start(client, lesson.id)

    left, right = exercise.correct_answer["pairs"][0]
    send_pair(client, lesson.id, attempt, exercise.id, left, right)

    response = client.post(
        f"/api/v1/lessons/{lesson.id}/complete", json={"attempt_id": attempt}
    )

    assert response.status_code == 409
    assert "answered" in response.json()["error"]["message"]


def test_the_whole_payload_endpoint_still_grades_match_pairs(
    client: TestClient, db_session: Session
) -> None:
    """`/answer` keeps working for match pairs.

    The UI no longer uses it, but it is a legitimate way to submit a finished
    answer and removing it would narrow the API for no gain. Both paths write the
    same row, and `UNIQUE(attempt_id, exercise_id)` means they cannot both write
    it.
    """
    lesson = first_lesson(db_session)
    exercise = match_exercise(db_session, lesson)
    attempt = start(client, lesson.id)

    response = client.post(
        f"/api/v1/lessons/{lesson.id}/answer",
        json={
            "attempt_id": attempt,
            "exercise_id": exercise.id,
            "answer": {
                "pairs": [list(p) for p in exercise.correct_answer["pairs"]]
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["correct"] is True
