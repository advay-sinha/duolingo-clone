"""The placement test, end to end.

The tests that matter most here are the *negative* ones. A placement test that
works is table stakes; a placement test that quietly awards XP, spends a heart,
extends a streak or marks a lesson complete would undermine every number the app
shows. Those four are asserted explicitly, and so is the property that stops them
being possible at all: no ``lesson_attempts`` row is ever written.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Exercise, LessonAttempt, PlacementAnswer, PlacementTest
from app.services.placement_engine import QUESTION_COUNT, STARTING_LEVEL

API = "/api/v1"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def course_id(client: TestClient) -> int:
    return client.get(f"{API}/courses").json()["courses"][0]["id"]


def begin_placement(client: TestClient) -> dict:
    """Walk onboarding as far as an open placement test, and start it."""
    client.post(f"{API}/onboarding/course", json={"course_id": course_id(client)})
    client.post(
        f"{API}/onboarding/proficiency", json={"proficiency": "BASIC_CONVERSATION"}
    )
    client.post(f"{API}/onboarding/start", json={"mode": "PLACEMENT"})

    response = client.post(f"{API}/placement/start")
    assert response.status_code == 200, response.text
    return response.json()


def right_answer(db: Session, exercise_id: int) -> dict[str, Any]:
    """A submission the grader will accept, read from the canonical answer.

    The test knows the answer because it can read the database. The *client*
    never can — ``ExercisePublic`` does not declare the field.
    """
    exercise = db.get(Exercise, exercise_id)
    answer = exercise.correct_answer

    if exercise.type.value == "MULTIPLE_CHOICE":
        return {"option_id": answer["option_id"]}
    if exercise.type.value == "TRANSLATE":
        return {"tokens": answer["accepted"][0].split()}
    return {"text": answer["accepted"][0]}


def wrong_answer(db: Session, exercise_id: int) -> dict[str, Any]:
    """A submission the grader will reject."""
    exercise = db.get(Exercise, exercise_id)

    if exercise.type.value == "MULTIPLE_CHOICE":
        correct = exercise.correct_answer["option_id"]
        other = next(o["id"] for o in exercise.data["options"] if o["id"] != correct)
        return {"option_id": other}
    if exercise.type.value == "TRANSLATE":
        return {"tokens": ["xyzzy"]}
    return {"text": "xyzzy"}


def answer_question(
    client: TestClient, db: Session, state: dict, *, correct: bool
) -> dict:
    """Answer whichever question the server is currently asking."""
    exercise_id = state["question"]["exercise"]["id"]
    payload = (
        right_answer(db, exercise_id) if correct else wrong_answer(db, exercise_id)
    )
    response = client.post(
        f"{API}/placement/answer",
        json={
            "test_id": state["test_id"],
            "exercise_id": exercise_id,
            "answer": payload,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def run_placement(client: TestClient, db: Session, *, correct: bool) -> dict:
    """Answer every question the same way, then complete the test."""
    state = begin_placement(client)
    while not state["finished"]:
        state = answer_question(client, db, state, correct=correct)

    response = client.post(
        f"{API}/placement/complete", json={"test_id": state["test_id"]}
    )
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------
# 5. The flow
# --------------------------------------------------------------------------


def test_placement_starts_at_the_middle_difficulty(register_user) -> None:
    client = register_user("pstart@example.com")
    state = begin_placement(client)

    assert state["question"]["difficulty"] == STARTING_LEVEL
    assert state["question"]["number"] == 1
    assert state["answered_count"] == 0
    assert state["total_questions"] == QUESTION_COUNT
    assert state["finished"] is False


def test_placement_questions_come_from_the_seeded_course(
    register_user, db_session: Session
) -> None:
    """Real exercises, not invented ones — the acceptance criterion, asserted."""
    client = register_user("pcontent@example.com")
    state = begin_placement(client)

    seen: list[int] = []
    while not state["finished"]:
        exercise_id = state["question"]["exercise"]["id"]
        seen.append(exercise_id)
        assert db_session.get(Exercise, exercise_id) is not None
        state = answer_question(client, db_session, state, correct=True)

    assert len(seen) == QUESTION_COUNT
    # No question is ever repeated: the adaptive rule reads its own history, so a
    # duplicate would not merely bore the learner, it would bend the test.
    assert len(set(seen)) == len(seen)


def test_a_placement_question_never_carries_its_answer(register_user) -> None:
    client = register_user("pleak@example.com")
    state = begin_placement(client)

    exercise = state["question"]["exercise"]
    assert "correct_answer" not in exercise
    assert "answer" not in exercise
    assert set(exercise) == {
        "id",
        "type",
        "order_index",
        "instruction",
        "prompt",
        "data",
    }


def test_placement_start_is_idempotent(register_user) -> None:
    """A refresh mid-test must resume, not restart."""
    client = register_user("presume@example.com")
    first = begin_placement(client)

    second = client.post(f"{API}/placement/start").json()
    assert second["test_id"] == first["test_id"]
    assert second["question"]["exercise"]["id"] == first["question"]["exercise"]["id"]


def test_answering_resumes_at_the_right_question_after_a_refresh(
    register_user, db_session: Session
) -> None:
    client = register_user("presume2@example.com")
    state = begin_placement(client)
    state = answer_question(client, db_session, state, correct=True)

    resumed = client.post(f"{API}/placement/start").json()
    assert resumed["answered_count"] == 1
    assert resumed["question"]["number"] == 2
    assert resumed["question"]["exercise"]["id"] == state["question"]["exercise"]["id"]


# --------------------------------------------------------------------------
# 7. Adaptive difficulty
# --------------------------------------------------------------------------


def test_a_correct_answer_makes_the_next_question_harder(
    register_user, db_session: Session
) -> None:
    client = register_user("padapt1@example.com")
    state = begin_placement(client)

    after = answer_question(client, db_session, state, correct=True)
    assert after["question"]["difficulty"] == STARTING_LEVEL + 1


def test_an_incorrect_answer_makes_the_next_question_easier(
    register_user, db_session: Session
) -> None:
    client = register_user("padapt2@example.com")
    state = begin_placement(client)

    after = answer_question(client, db_session, state, correct=False)
    assert after["question"]["difficulty"] == STARTING_LEVEL - 1


def test_difficulty_climbs_to_the_top_and_stays_there(
    register_user, db_session: Session
) -> None:
    client = register_user("padapt3@example.com")
    state = begin_placement(client)

    difficulties = [state["question"]["difficulty"]]
    while not state["finished"]:
        state = answer_question(client, db_session, state, correct=True)
        if state["question"]:
            difficulties.append(state["question"]["difficulty"])

    assert difficulties[0] == 3
    assert difficulties[1] == 4
    assert difficulties[2] == 5
    assert difficulties[3:] == [5] * len(difficulties[3:])


def test_difficulty_falls_to_the_bottom_and_stays_there(
    register_user, db_session: Session
) -> None:
    client = register_user("padapt4@example.com")
    state = begin_placement(client)

    difficulties = []
    while not state["finished"]:
        state = answer_question(client, db_session, state, correct=False)
        if state["question"]:
            difficulties.append(state["question"]["difficulty"])

    assert difficulties[:2] == [2, 1]
    assert all(level == 1 for level in difficulties[1:])


# --------------------------------------------------------------------------
# 6. Scoring
# --------------------------------------------------------------------------


def test_a_perfect_test_places_the_learner_at_the_last_skill(
    register_user, db_session: Session
) -> None:
    client = register_user("pperfect@example.com")
    result = run_placement(client, db_session, correct=True)

    assert result["level"] == 5
    assert result["correct_answers"] == QUESTION_COUNT
    assert result["score"] == result["max_score"]

    path = client.get(f"{API}/courses/{course_id(client)}/path").json()
    skills = [skill for unit in path["units"] for skill in unit["skills"]]
    assert result["skill_id"] == skills[-1]["id"]
    assert result["skills_placed_out"] == len(skills) - 1


def test_a_failed_test_places_the_learner_at_the_first_skill(
    register_user, db_session: Session
) -> None:
    """Performing poorly is not a failure state — it is the same starting point
    "start from scratch" would have given, and it cost the learner nothing."""
    client = register_user("pfail@example.com")
    result = run_placement(client, db_session, correct=False)

    assert result["level"] == 0
    assert result["correct_answers"] == 0
    assert result["score"] == 0
    assert result["skills_placed_out"] == 0

    path = client.get(f"{API}/courses/{course_id(client)}/path").json()
    skills = [skill for unit in path["units"] for skill in unit["skills"]]
    assert result["skill_id"] == skills[0]["id"]
    assert skills[0]["state"] == "AVAILABLE"
    assert all(skill["placed_out"] is False for skill in skills)


def test_the_backend_computes_the_level_and_the_client_cannot_ask_for_one(
    register_user, db_session: Session
) -> None:
    """The request body has no level field, and sending one changes nothing."""
    client = register_user("pauthority@example.com")
    state = begin_placement(client)

    while not state["finished"]:
        exercise_id = state["question"]["exercise"]["id"]
        response = client.post(
            f"{API}/placement/answer",
            json={
                "test_id": state["test_id"],
                "exercise_id": exercise_id,
                "answer": wrong_answer(db_session, exercise_id),
                # Every one of these is ignored: no schema declares them.
                "difficulty": 5,
                "level": 5,
                "is_correct": True,
            },
        )
        assert response.json()["correct"] is False
        state = response.json()

    result = client.post(
        f"{API}/placement/complete",
        json={"test_id": state["test_id"], "level": 5},
    ).json()
    assert result["level"] == 0


# --------------------------------------------------------------------------
# 8. The result persists, and shapes the path
# --------------------------------------------------------------------------


def test_the_placement_result_persists_across_logout_and_login(
    register_user, db_session: Session
) -> None:
    client = register_user("ppersist@example.com")
    result = run_placement(client, db_session, correct=True)

    client.post(f"{API}/auth/logout")
    client.post(
        f"{API}/auth/login",
        json={"email": "ppersist@example.com", "password": "password123"},
    )

    status = client.get(f"{API}/onboarding").json()
    assert status["completed"] is True
    assert status["step"] == "DONE"
    assert status["starting_mode"] == "PLACEMENT"
    assert status["placement"]["level"] == result["level"]
    assert status["placement"]["skill_id"] == result["skill_id"]


def test_earlier_skills_report_placed_out_rather_than_completed(
    register_user, db_session: Session
) -> None:
    """**The semantic distinction the brief calls important.**

    The learner did not do these lessons, and the path does not say they did.
    """
    client = register_user("pplaced@example.com")
    run_placement(client, db_session, correct=True)

    path = client.get(f"{API}/courses/{course_id(client)}/path").json()
    skills = [skill for unit in path["units"] for skill in unit["skills"]]

    assert [skill["state"] for skill in skills[:-1]] == ["PLACED_OUT"] * (
        len(skills) - 1
    )
    assert skills[-1]["state"] == "AVAILABLE"

    for skill in skills[:-1]:
        assert skill["placed_out"] is True
        # Placed out, not completed: no crowns, no lessons done, no XP.
        assert skill["crowns"] == 0
        assert skill["lessons_completed"] == 0
        assert skill["xp_earned"] == 0
        assert all(lesson["completed"] is False for lesson in skill["lessons"])


def test_a_placed_out_learner_can_still_study_the_skills_they_skipped(
    register_user, db_session: Session
) -> None:
    """Placed out is not locked. The material is still there to be learned."""
    client = register_user("pstudy@example.com")
    run_placement(client, db_session, correct=True)

    path = client.get(f"{API}/courses/{course_id(client)}/path").json()
    first_skill = path["units"][0]["skills"][0]
    lesson_id = first_skill["lessons"][0]["id"]

    assert first_skill["state"] == "PLACED_OUT"
    assert client.post(f"{API}/lessons/{lesson_id}/start").status_code == 200


# --------------------------------------------------------------------------
# 13-16. Placement is an assessment and nothing else
# --------------------------------------------------------------------------


def test_placement_awards_no_xp(register_user, db_session: Session) -> None:
    client = register_user("pxp@example.com")
    run_placement(client, db_session, correct=True)

    assert client.get(f"{API}/users/me/stats").json()["total_xp"] == 0


def test_placement_consumes_no_hearts(register_user, db_session: Session) -> None:
    """Every answer wrong, and every heart still there."""
    client = register_user("phearts@example.com")
    run_placement(client, db_session, correct=False)

    stats = client.get(f"{API}/users/me/stats").json()
    assert stats["hearts"] == stats["max_hearts"] == 5


def test_placement_does_not_increment_the_streak(
    register_user, db_session: Session
) -> None:
    client = register_user("pstreak@example.com")
    run_placement(client, db_session, correct=True)

    stats = client.get(f"{API}/users/me/stats").json()
    assert stats["current_streak"] == 0
    assert stats["longest_streak"] == 0
    assert stats["daily_xp"] == 0


def test_placement_creates_no_lesson_attempt(
    register_user, db_session: Session
) -> None:
    """The structural guarantee under the three assertions above.

    Every gamification rule in the codebase is written against "there is an
    attempt". No attempt, no possible award — it is not a flag anyone has to
    remember to check.
    """
    client = register_user("pattempt@example.com")
    user_id = client.get(f"{API}/auth/me").json()["user"]["id"]
    run_placement(client, db_session, correct=True)

    attempts = (
        db_session.query(LessonAttempt).filter(LessonAttempt.user_id == user_id).count()
    )
    assert attempts == 0


def test_placement_unlocks_no_achievements(
    register_user, db_session: Session
) -> None:
    client = register_user("pach@example.com")
    run_placement(client, db_session, correct=True)

    body = client.get(f"{API}/users/me/achievements").json()
    assert body["unlocked_count"] == 0


# --------------------------------------------------------------------------
# 20 + idempotency and validation
# --------------------------------------------------------------------------


def test_completing_the_placement_test_twice_returns_the_same_result(
    register_user, db_session: Session
) -> None:
    client = register_user("pidem@example.com")
    first = run_placement(client, db_session, correct=True)

    second = client.post(
        f"{API}/placement/complete", json={"test_id": first["test_id"]}
    )
    assert second.status_code == 200
    assert second.json()["level"] == first["level"]
    assert second.json()["skill_id"] == first["skill_id"]


def test_resubmitting_an_answer_replays_the_verdict(
    register_user, db_session: Session
) -> None:
    """A retried request after a dropped response must not add a second answer:
    it would feed the adaptive walk an extra data point and change the test."""
    client = register_user("preplay@example.com")
    state = begin_placement(client)
    exercise_id = state["question"]["exercise"]["id"]

    payload = {
        "test_id": state["test_id"],
        "exercise_id": exercise_id,
        "answer": right_answer(db_session, exercise_id),
    }
    first = client.post(f"{API}/placement/answer", json=payload).json()
    second = client.post(f"{API}/placement/answer", json=payload).json()

    assert first["already_answered"] is False
    assert second["already_answered"] is True
    assert second["correct"] == first["correct"]
    assert second["answered_count"] == first["answered_count"] == 1

    rows = (
        db_session.query(PlacementAnswer)
        .filter(PlacementAnswer.test_id == state["test_id"])
        .count()
    )
    assert rows == 1


def test_answering_a_question_that_was_not_asked_is_refused(
    register_user, db_session: Session
) -> None:
    """Otherwise a caller could choose which difficulty to be assessed at."""
    client = register_user("pwrongq@example.com")
    state = begin_placement(client)

    asked = state["question"]["exercise"]["id"]
    other = db_session.query(Exercise).filter(Exercise.id != asked).first()

    response = client.post(
        f"{API}/placement/answer",
        json={
            "test_id": state["test_id"],
            "exercise_id": other.id,
            "answer": {"text": "whatever"},
        },
    )
    assert response.status_code == 409


def test_a_malformed_answer_is_a_422_and_is_not_recorded(
    register_user, db_session: Session
) -> None:
    """A client bug is not a wrong answer, and must not move the level."""
    client = register_user("pmalformed@example.com")
    state = begin_placement(client)

    response = client.post(
        f"{API}/placement/answer",
        json={
            "test_id": state["test_id"],
            "exercise_id": state["question"]["exercise"]["id"],
            "answer": {"nonsense": True},
        },
    )
    assert response.status_code == 422

    rows = (
        db_session.query(PlacementAnswer)
        .filter(PlacementAnswer.test_id == state["test_id"])
        .count()
    )
    assert rows == 0


def test_completing_an_unfinished_test_is_refused(register_user) -> None:
    client = register_user("pearly@example.com")
    state = begin_placement(client)

    response = client.post(
        f"{API}/placement/complete", json={"test_id": state["test_id"]}
    )
    assert response.status_code == 409


def test_answering_a_finished_test_is_refused(
    register_user, db_session: Session
) -> None:
    client = register_user("pafter@example.com")
    state = begin_placement(client)
    first_exercise = state["question"]["exercise"]["id"]
    result = run_placement_from(client, db_session, state)

    response = client.post(
        f"{API}/placement/answer",
        json={
            "test_id": result["test_id"],
            "exercise_id": first_exercise,
            "answer": {"text": "x"},
        },
    )
    assert response.status_code == 409


def run_placement_from(client: TestClient, db: Session, state: dict) -> dict:
    """Finish an already-started test."""
    while not state["finished"]:
        state = answer_question(client, db, state, correct=True)
    return client.post(
        f"{API}/placement/complete", json={"test_id": state["test_id"]}
    ).json()


# --------------------------------------------------------------------------
# 17. Isolation
# --------------------------------------------------------------------------


def test_one_learner_cannot_answer_into_anothers_placement_test(
    register_user, db_session: Session
) -> None:
    alice = register_user("alice-p@example.com")
    bob = register_user("bob-p@example.com")

    alice_state = begin_placement(alice)
    begin_placement(bob)

    response = bob.post(
        f"{API}/placement/answer",
        json={
            "test_id": alice_state["test_id"],
            "exercise_id": alice_state["question"]["exercise"]["id"],
            "answer": right_answer(
                db_session, alice_state["question"]["exercise"]["id"]
            ),
        },
    )
    assert response.status_code == 403


def test_one_learner_cannot_complete_anothers_placement_test(
    register_user, db_session: Session
) -> None:
    alice = register_user("alice-pc@example.com")
    bob = register_user("bob-pc@example.com")

    alice_state = begin_placement(alice)
    while not alice_state["finished"]:
        alice_state = answer_question(alice, db_session, alice_state, correct=True)

    begin_placement(bob)
    response = bob.post(
        f"{API}/placement/complete", json={"test_id": alice_state["test_id"]}
    )
    assert response.status_code == 403

    # Alice's test is untouched and she can still complete it herself.
    assert (
        alice.post(
            f"{API}/placement/complete", json={"test_id": alice_state["test_id"]}
        ).status_code
        == 200
    )


def test_placement_results_do_not_leak_between_learners(
    register_user, db_session: Session
) -> None:
    alice = register_user("alice-pr@example.com")
    bob = register_user("bob-pr@example.com")

    run_placement(alice, db_session, correct=True)

    bob_path = bob.get(f"{API}/courses/{course_id(bob)}/path").json()
    bob_skills = [skill for unit in bob_path["units"] for skill in unit["skills"]]
    assert all(skill["placed_out"] is False for skill in bob_skills)
    assert bob_skills[0]["state"] == "AVAILABLE"
    assert bob_skills[1]["state"] == "LOCKED"


def test_placement_requires_a_session(anon_client: TestClient) -> None:
    assert anon_client.post(f"{API}/placement/start").status_code == 401
    assert (
        anon_client.post(
            f"{API}/placement/answer",
            json={"test_id": 1, "exercise_id": 1, "answer": {}},
        ).status_code
        == 401
    )
    assert (
        anon_client.post(f"{API}/placement/complete", json={"test_id": 1}).status_code
        == 401
    )


def test_placement_requires_choosing_find_my_level(register_user) -> None:
    """The placement endpoints are not a back door around the flow."""
    client = register_user("pmode@example.com")
    client.post(f"{API}/onboarding/course", json={"course_id": course_id(client)})

    assert client.post(f"{API}/placement/start").status_code == 409

    client.post(f"{API}/onboarding/proficiency", json={"proficiency": "BEGINNER"})
    client.post(f"{API}/onboarding/start", json={"mode": "SCRATCH"})

    assert client.post(f"{API}/placement/start").status_code == 409


def test_a_placement_test_row_records_its_own_result(
    register_user, db_session: Session
) -> None:
    """The score is a historical fact, stored rather than recomputed on read."""
    client = register_user("prow@example.com")
    result = run_placement(client, db_session, correct=True)

    test = db_session.get(PlacementTest, result["test_id"])
    assert test.completed_at is not None
    assert test.result_level == result["level"]
    assert test.result_score == result["score"]
    assert test.result_skill_id == result["skill_id"]
