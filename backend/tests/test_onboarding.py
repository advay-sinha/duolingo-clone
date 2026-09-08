"""The onboarding flow, end to end through the API.

Two properties get the most attention here, because they are the two the feature
could most easily get wrong:

* **Existing learners must not be dragged into onboarding.** The seeded learner
  has no onboarding row, and every assertion about them is that nothing happened.
* **The server owns the sequence.** Steps are enforced in order, state survives
  logout and login, and no request carries a user id.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import LessonAttempt, UserOnboarding

API = "/api/v1"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def course_id(client: TestClient) -> int:
    """The id of the one seeded course."""
    return client.get(f"{API}/courses").json()["courses"][0]["id"]


def status_of(client: TestClient) -> dict:
    response = client.get(f"{API}/onboarding")
    assert response.status_code == 200, response.text
    return response.json()


def choose_course(client: TestClient, cid: int | None = None):
    return client.post(
        f"{API}/onboarding/course",
        json={"course_id": cid if cid is not None else course_id(client)},
    )


def choose_proficiency(client: TestClient, value: str = "BASIC_CONVERSATION"):
    return client.post(f"{API}/onboarding/proficiency", json={"proficiency": value})


def choose_start(client: TestClient, mode: str):
    return client.post(f"{API}/onboarding/start", json={"mode": mode})


# --------------------------------------------------------------------------
# 1. A new learner starts at the beginning
# --------------------------------------------------------------------------


def test_a_new_learner_starts_at_the_course_step(register_user) -> None:
    client = register_user("new@example.com")
    body = status_of(client)

    assert body["completed"] is False
    assert body["step"] == "COURSE"
    assert body["course_id"] is None
    assert body["proficiency"] is None
    assert body["starting_mode"] is None
    assert body["grandfathered"] is False


def test_registration_creates_the_onboarding_row(register_user, db_session: Session) -> None:
    """Written in the same transaction as the user, which is what makes the
    absence of a row mean 'this learner predates onboarding'."""
    client = register_user("row@example.com")
    user_id = client.get(f"{API}/auth/me").json()["user"]["id"]

    assert db_session.get(UserOnboarding, user_id) is not None


# --------------------------------------------------------------------------
# 2-3. Choices persist
# --------------------------------------------------------------------------


def test_course_selection_persists(register_user) -> None:
    client = register_user("course@example.com")
    cid = course_id(client)

    body = choose_course(client, cid).json()
    assert body["course_id"] == cid
    assert body["step"] == "PROFICIENCY"

    assert status_of(client)["course_id"] == cid


def test_proficiency_persists(register_user) -> None:
    client = register_user("prof@example.com")
    choose_course(client)

    body = choose_proficiency(client, "VARIOUS_TOPICS").json()
    assert body["proficiency"] == "VARIOUS_TOPICS"
    assert body["step"] == "START"

    assert status_of(client)["proficiency"] == "VARIOUS_TOPICS"


def test_all_five_proficiency_values_are_accepted(register_user) -> None:
    for index, value in enumerate(
        [
            "BEGINNER",
            "COMMON_WORDS",
            "BASIC_CONVERSATION",
            "VARIOUS_TOPICS",
            "ADVANCED",
        ]
    ):
        client = register_user(f"prof{index}@example.com")
        choose_course(client)
        assert choose_proficiency(client, value).status_code == 200


def test_an_unknown_proficiency_is_rejected_by_the_schema(register_user) -> None:
    """The enum is the validation. A free-form string would put this check in
    application code, where it could be forgotten."""
    client = register_user("badprof@example.com")
    choose_course(client)

    response = choose_proficiency(client, "FLUENT")
    assert response.status_code == 422


def test_onboarding_state_survives_logout_and_login(register_user) -> None:
    client = register_user("persist@example.com")
    cid = course_id(client)
    choose_course(client, cid)
    choose_proficiency(client, "COMMON_WORDS")

    client.post(f"{API}/auth/logout")
    assert client.get(f"{API}/onboarding").status_code == 401

    client.post(
        f"{API}/auth/login",
        json={"email": "persist@example.com", "password": "password123"},
    )

    body = status_of(client)
    assert body["course_id"] == cid
    assert body["proficiency"] == "COMMON_WORDS"
    assert body["step"] == "START"


# --------------------------------------------------------------------------
# 4 + 9. Start from scratch
# --------------------------------------------------------------------------


def test_start_from_scratch_completes_onboarding(register_user) -> None:
    client = register_user("scratch@example.com")
    choose_course(client)
    choose_proficiency(client)

    body = choose_start(client, "SCRATCH").json()
    assert body["completed"] is True
    assert body["step"] == "DONE"
    assert body["starting_mode"] == "SCRATCH"
    assert body["completed_at"] is not None
    assert body["placement"] is None


def test_start_from_scratch_awards_nothing(register_user, db_session: Session) -> None:
    """No XP, no crowns, no lesson attempt — the decision is all that is written."""
    client = register_user("scratch2@example.com")
    user_id = client.get(f"{API}/auth/me").json()["user"]["id"]
    choose_course(client)
    choose_proficiency(client)
    choose_start(client, "SCRATCH")

    stats = client.get(f"{API}/users/me/stats").json()
    assert stats["total_xp"] == 0
    assert stats["hearts"] == 5
    assert stats["current_streak"] == 0

    attempts = (
        db_session.query(LessonAttempt).filter(LessonAttempt.user_id == user_id).count()
    )
    assert attempts == 0


def test_start_from_scratch_leaves_the_first_skill_available(register_user) -> None:
    """From the unchanged Phase 3 rule, with no special case for a new learner."""
    client = register_user("scratch3@example.com")
    cid = course_id(client)
    choose_course(client, cid)
    choose_proficiency(client)
    choose_start(client, "SCRATCH")

    path = client.get(f"{API}/courses/{cid}/path").json()
    skills = [skill for unit in path["units"] for skill in unit["skills"]]

    assert skills[0]["state"] == "AVAILABLE"
    assert all(skill["state"] == "LOCKED" for skill in skills[1:])
    assert all(skill["placed_out"] is False for skill in skills)


# --------------------------------------------------------------------------
# 10. The steps are ordered, and the server enforces the order
# --------------------------------------------------------------------------


def test_proficiency_before_a_course_is_refused(register_user) -> None:
    client = register_user("order1@example.com")
    response = choose_proficiency(client)
    assert response.status_code == 409


def test_a_starting_point_before_a_proficiency_is_refused(register_user) -> None:
    client = register_user("order2@example.com")
    choose_course(client)
    response = choose_start(client, "SCRATCH")
    assert response.status_code == 409


def test_a_refreshed_learner_is_returned_to_the_step_they_were_on(
    register_user,
) -> None:
    """There is no client state to lose: the step is recomputed on every read."""
    client = register_user("refresh@example.com")
    choose_course(client)

    for _ in range(3):
        assert status_of(client)["step"] == "PROFICIENCY"

    choose_proficiency(client)
    for _ in range(3):
        assert status_of(client)["step"] == "START"


# --------------------------------------------------------------------------
# 11. Existing learners bypass onboarding entirely
# --------------------------------------------------------------------------


def test_the_seeded_learner_has_no_onboarding_row(client: TestClient, db_session: Session) -> None:
    user_id = client.get(f"{API}/auth/me").json()["user"]["id"]
    assert db_session.get(UserOnboarding, user_id) is None


def test_an_existing_learner_is_reported_complete(client: TestClient) -> None:
    """The whole 'do not break existing users' rule, in one assertion."""
    body = status_of(client)

    assert body["completed"] is True
    assert body["step"] == "DONE"
    assert body["grandfathered"] is True


def test_an_existing_learner_cannot_be_pushed_back_into_onboarding(
    client: TestClient,
) -> None:
    """Every write endpoint refuses them, so no code path creates a row for a
    learner who finished the flow the day they signed up."""
    assert choose_course(client).status_code == 409
    assert choose_proficiency(client).status_code == 409
    assert choose_start(client, "SCRATCH").status_code == 409
    assert client.post(f"{API}/placement/start").status_code == 409


def test_a_completed_learner_cannot_redo_onboarding(register_user) -> None:
    client = register_user("done@example.com")
    choose_course(client)
    choose_proficiency(client)
    choose_start(client, "SCRATCH")

    assert choose_course(client).status_code == 409
    assert choose_proficiency(client).status_code == 409
    assert choose_start(client, "PLACEMENT").status_code == 409


def test_onboarding_never_blocks_the_lesson_engine(register_user) -> None:
    """A deliberate scope decision, recorded as a test.

    Onboarding is a routing concern backed by server state, not an authorisation
    boundary. Gating the lesson API on it would add a check to every endpoint to
    protect against nothing — a learner who bypasses the screens has skipped a
    questionnaire, not gained access to anything.
    """
    client = register_user("mid@example.com")
    assert status_of(client)["completed"] is False

    lessons = client.get(f"{API}/courses/{course_id(client)}/path").json()
    first_lesson = lessons["units"][0]["skills"][0]["lessons"][0]["id"]
    assert client.post(f"{API}/lessons/{first_lesson}/start").status_code == 200


# --------------------------------------------------------------------------
# 12 + 17. Isolation
# --------------------------------------------------------------------------


def test_one_learner_cannot_read_anothers_onboarding(register_user) -> None:
    alice = register_user("alice-onb@example.com")
    bob = register_user("bob-onb@example.com")

    choose_course(alice)
    choose_proficiency(alice, "ADVANCED")

    assert status_of(bob)["step"] == "COURSE"
    assert status_of(bob)["proficiency"] is None


def test_one_learner_cannot_modify_anothers_onboarding(register_user) -> None:
    """Not by any request they can construct: there is no user id field."""
    alice = register_user("alice-mod@example.com")
    bob = register_user("bob-mod@example.com")

    alice_id = alice.get(f"{API}/auth/me").json()["user"]["id"]

    choose_course(bob)
    choose_proficiency(bob, "BEGINNER")
    choose_start(bob, "SCRATCH")

    # Alice is untouched by everything Bob did.
    assert status_of(alice)["completed"] is False
    assert status_of(alice)["step"] == "COURSE"

    # And an explicit attempt to name her changes nothing: the field is ignored
    # because no schema declares it.
    bob.post(
        f"{API}/onboarding/course",
        json={"course_id": course_id(bob), "user_id": alice_id},
    )
    assert status_of(alice)["course_id"] is None


def test_onboarding_requires_a_session(anon_client: TestClient) -> None:
    assert anon_client.get(f"{API}/onboarding").status_code == 401
    assert (
        anon_client.post(f"{API}/onboarding/course", json={"course_id": 1}).status_code
        == 401
    )
    assert (
        anon_client.post(
            f"{API}/onboarding/proficiency", json={"proficiency": "BEGINNER"}
        ).status_code
        == 401
    )
    assert (
        anon_client.post(f"{API}/onboarding/start", json={"mode": "SCRATCH"}).status_code
        == 401
    )


# --------------------------------------------------------------------------
# 18-19. Course validation
# --------------------------------------------------------------------------


def test_an_unknown_course_is_rejected(register_user) -> None:
    client = register_user("badcourse@example.com")
    response = choose_course(client, 9999)

    assert response.status_code == 404
    assert status_of(client)["course_id"] is None


def test_a_coming_soon_course_cannot_be_selected(register_user) -> None:
    """The 'coming soon' tiles are presentation with no row behind them.

    That is what makes them unselectable — not the CSS. A hand-written request
    naming any id the courses table does not contain is refused, and the seeded
    database contains exactly one course.
    """
    client = register_user("soon@example.com")
    real = {course["id"] for course in client.get(f"{API}/courses").json()["courses"]}

    assert len(real) == 1
    for fake_id in (real.pop() + 1, 42, 100):
        assert choose_course(client, fake_id).status_code == 404


def test_the_seeded_course_is_the_spanish_one(client: TestClient) -> None:
    """Guards the assumption every "only Spanish is selectable" claim rests on."""
    courses = client.get(f"{API}/courses").json()["courses"]

    assert len(courses) == 1
    assert courses[0]["target_language"] == "Spanish"
    assert courses[0]["source_language"] == "English"


def test_the_demo_learner_login_still_works(client: TestClient) -> None:
    """Sanity: the grandfathering rule did not change how anyone signs in."""
    settings = get_settings()
    response = client.post(
        f"{API}/auth/login",
        json={
            "email": settings.demo_email,
            "password": settings.demo_user_password,
        },
    )
    assert response.status_code == 200
