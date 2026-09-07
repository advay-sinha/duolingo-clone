"""Tests for GET /api/v1/courses/{course_id}/path.

The unlock tests are the important ones. They prove the rule genuinely lives in
``PathService`` and is computed from stored progress — not stored as a flag, and
not hardcoded into the response.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, LessonAttempt, Skill, User, UserSkillProgress


def path_of(client: TestClient, db_session: Session) -> dict:
    """Fetch the path for the seeded course."""
    course_id = db_session.scalar(select(Course.id))
    response = client.get(f"/api/v1/courses/{course_id}/path")
    assert response.status_code == 200
    return response.json()


def flat_skills(body: dict) -> list[dict]:
    """Every skill in course order, flattened across units."""
    return [skill for unit in body["units"] for skill in unit["skills"]]


def award_crown(db_session: Session, skill_index: int) -> None:
    """Give the learner a crown on the nth skill, in course order.

    Writes only to ``user_skill_progress`` — the same row lesson completion will
    update in Phase 4. Nothing sets a state flag, because no such column exists.
    """
    user = db_session.scalar(select(User))
    skills = db_session.scalars(select(Skill).order_by(Skill.id)).all()
    skill = skills[skill_index]

    progress = db_session.scalar(
        select(UserSkillProgress).where(
            UserSkillProgress.user_id == user.id,
            UserSkillProgress.skill_id == skill.id,
        )
    )
    progress.crowns = 1
    progress.lessons_completed = len(skill.lessons)
    db_session.commit()


# --------------------------------------------------------------------------
# Structure
# --------------------------------------------------------------------------


def test_valid_course_returns_200(client: TestClient, db_session: Session) -> None:
    assert path_of(client, db_session)["course_title"] == "Spanish"


def test_the_path_has_the_seeded_shape(
    client: TestClient, db_session: Session
) -> None:
    body = path_of(client, db_session)

    assert len(body["units"]) == 3
    assert len(flat_skills(body)) == 9
    assert sum(len(s["lessons"]) for s in flat_skills(body)) == 18
    assert all(len(s["lessons"]) == 2 for s in flat_skills(body))


def test_nested_ordering_is_correct(
    client: TestClient, db_session: Session
) -> None:
    """Order is a property of the response, not something the client must sort."""
    body = path_of(client, db_session)

    assert [u["order_index"] for u in body["units"]] == [0, 1, 2]
    for unit in body["units"]:
        assert [s["order_index"] for s in unit["skills"]] == [0, 1, 2]
        for skill in unit["skills"]:
            assert [lesson["order_index"] for lesson in skill["lessons"]] == [0, 1]


def test_exercises_are_not_included_in_the_path(
    client: TestClient, db_session: Session
) -> None:
    """The path screen never shows exercises; loading 90 rows would be waste."""
    for skill in flat_skills(path_of(client, db_session)):
        for lesson in skill["lessons"]:
            assert "exercises" not in lesson


def test_nonexistent_course_returns_404(client: TestClient) -> None:
    """Not an empty 200 — a typo'd id must be distinguishable from an empty course."""
    response = client.get("/api/v1/courses/999999/path")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_a_non_integer_course_id_is_rejected(client: TestClient) -> None:
    """FastAPI validates the path parameter before the route body runs."""
    assert client.get("/api/v1/courses/abc/path").status_code == 422


# --------------------------------------------------------------------------
# Derived unlock state — the core business rule
# --------------------------------------------------------------------------


def test_initially_only_the_first_skill_is_available(
    client: TestClient, db_session: Session
) -> None:
    skills = flat_skills(path_of(client, db_session))

    assert skills[0]["state"] == "AVAILABLE"
    assert all(skill["state"] == "LOCKED" for skill in skills[1:])


def test_completing_the_first_skill_unlocks_the_second(
    client: TestClient, db_session: Session
) -> None:
    award_crown(db_session, 0)

    skills = flat_skills(path_of(client, db_session))

    assert skills[0]["state"] == "COMPLETED"
    assert skills[1]["state"] == "AVAILABLE"
    assert skills[2]["state"] == "LOCKED"
    assert all(skill["state"] == "LOCKED" for skill in skills[2:])


def test_completing_the_second_skill_unlocks_the_third(
    client: TestClient, db_session: Session
) -> None:
    award_crown(db_session, 0)
    award_crown(db_session, 1)

    skills = flat_skills(path_of(client, db_session))

    assert skills[0]["state"] == "COMPLETED"
    assert skills[1]["state"] == "COMPLETED"
    assert skills[2]["state"] == "AVAILABLE"
    assert skills[3]["state"] == "LOCKED"


def test_unlocking_carries_across_a_unit_boundary(
    client: TestClient, db_session: Session
) -> None:
    """The predecessor of a unit's first skill is the last skill of the previous
    unit, so the ordering that drives unlocking is global, not per unit."""
    for index in range(3):  # complete all three skills of unit 1
        award_crown(db_session, index)

    body = path_of(client, db_session)
    unit_two_first_skill = body["units"][1]["skills"][0]

    assert unit_two_first_skill["state"] == "AVAILABLE"


def test_a_completed_skill_stays_completed_and_does_not_relock(
    client: TestClient, db_session: Session
) -> None:
    award_crown(db_session, 0)
    award_crown(db_session, 1)

    skills = flat_skills(path_of(client, db_session))

    assert skills[0]["state"] == "COMPLETED"


def test_no_state_columns_exist_in_the_database(db_session: Session) -> None:
    """State is derived. This asserts the schema never grew a shortcut."""
    from app.models import Skill as SkillModel

    columns = set(SkillModel.__table__.columns.keys())
    assert not columns & {"is_locked", "is_available", "is_completed", "state"}

    progress_columns = set(UserSkillProgress.__table__.columns.keys())
    assert not progress_columns & {"is_locked", "is_available", "is_completed", "state"}


# --------------------------------------------------------------------------
# Lesson completion
# --------------------------------------------------------------------------


def test_lessons_start_uncompleted(client: TestClient, db_session: Session) -> None:
    for skill in flat_skills(path_of(client, db_session)):
        assert all(not lesson["completed"] for lesson in skill["lessons"])
        assert skill["lessons_completed"] == 0
        assert skill["total_lessons"] == 2


def test_a_completed_attempt_marks_its_lesson_completed(
    client: TestClient, db_session: Session
) -> None:
    """Lesson completion is derived from attempt history, not a lesson column."""
    user = db_session.scalar(select(User))
    skill = db_session.scalars(select(Skill).order_by(Skill.id)).first()
    lesson = skill.lessons[0]

    db_session.add(
        LessonAttempt(
            user_id=user.id,
            lesson_id=lesson.id,
            completed=True,
            completed_at=datetime.now(timezone.utc),
            correct_answers=5,
        )
    )
    db_session.commit()

    first_skill = flat_skills(path_of(client, db_session))[0]

    assert first_skill["lessons_completed"] == 1
    assert first_skill["total_lessons"] == 2
    assert first_skill["lessons"][0]["completed"] is True
    assert first_skill["lessons"][1]["completed"] is False
    # Progress without a crown does not unlock the next skill.
    assert first_skill["state"] == "AVAILABLE"


def test_an_incomplete_attempt_does_not_count(
    client: TestClient, db_session: Session
) -> None:
    user = db_session.scalar(select(User))
    lesson = db_session.scalars(select(Skill).order_by(Skill.id)).first().lessons[0]

    db_session.add(
        LessonAttempt(user_id=user.id, lesson_id=lesson.id, completed=False)
    )
    db_session.commit()

    first_skill = flat_skills(path_of(client, db_session))[0]
    assert first_skill["lessons_completed"] == 0


def test_the_response_carries_counts_but_not_a_percentage(
    client: TestClient, db_session: Session
) -> None:
    """One representation of progress, owned by the server; the ratio is the
    client's to render."""
    skill = flat_skills(path_of(client, db_session))[0]

    assert "lessons_completed" in skill and "total_lessons" in skill
    assert "progress_percentage" not in skill
    assert "progress" not in skill
