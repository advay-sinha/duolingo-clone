"""Registration, login, logout, and who the session says you are.

The suite deliberately goes through HTTP rather than calling ``auth_service``
directly: the cookie, the status codes and the response shape are as much of the
contract as the hashing is, and a test that skipped them would pass while a
browser failed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Session as SessionRow
from app.models import User, UserSkillProgress, UserStats
from app.services import auth_service

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"


def payload(**over) -> dict:
    return {
        "email": "alice@example.com",
        "password": "password123",
        "display_name": "Alice",
        **over,
    }


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------


def test_registration_creates_an_account_and_signs_it_in(
    anon_client: TestClient, db_session: Session
) -> None:
    response = anon_client.post(REGISTER, json=payload())

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "alice@example.com"
    assert body["user"]["display_name"] == "Alice"

    # The session cookie is set, so the very next request is authenticated —
    # nobody is asked to type credentials they just chose.
    assert get_settings().session_cookie_name in response.cookies
    assert anon_client.get(ME).json()["user"]["display_name"] == "Alice"


def test_registration_initialises_a_full_learner(
    anon_client: TestClient, db_session: Session
) -> None:
    """Every row the app's screens assume exists is created, with zeroed state."""
    anon_client.post(REGISTER, json=payload())

    user = db_session.scalar(select(User).where(User.email == "alice@example.com"))
    stats = db_session.get(UserStats, user.id)

    assert stats is not None
    assert (stats.total_xp, stats.gems, stats.current_streak, stats.daily_xp) == (
        0,
        0,
        0,
        0,
    )
    assert stats.hearts == get_settings().max_hearts

    progress = db_session.scalars(
        select(UserSkillProgress).where(UserSkillProgress.user_id == user.id)
    ).all()
    assert len(progress) == 9  # one per seeded skill
    assert all(row.crowns == 0 and row.lessons_completed == 0 for row in progress)


def test_a_new_learner_sees_only_the_first_skill_unlocked(
    register_user, db_session: Session
) -> None:
    """No special case for "new user" — the existing path rule just works."""
    client = register_user("bob@example.com")

    path = client.get("/api/v1/courses/1/path").json()
    states = [
        skill["state"] for unit in path["units"] for skill in unit["skills"]
    ]

    assert states[0] == "AVAILABLE"
    assert set(states[1:]) == {"LOCKED"}


def test_the_password_is_hashed_not_stored(
    anon_client: TestClient, db_session: Session
) -> None:
    anon_client.post(REGISTER, json=payload())

    user = db_session.scalar(select(User).where(User.email == "alice@example.com"))

    assert user.password_hash != "password123"
    assert user.password_hash.startswith("$2b$")  # bcrypt, with cost and salt
    assert auth_service.verify_password("password123", user.password_hash)


def test_two_learners_with_the_same_password_get_different_hashes(
    register_user, db_session: Session
) -> None:
    """Proves the hash is salted — otherwise identical passwords would collide."""
    register_user("a@example.com", password="password123", display_name="A")
    register_user("b@example.com", password="password123", display_name="B")

    hashes = db_session.scalars(
        select(User.password_hash).where(User.email.in_(["a@example.com", "b@example.com"]))
    ).all()

    assert hashes[0] != hashes[1]


def test_the_password_never_appears_in_the_response(anon_client: TestClient) -> None:
    response = anon_client.post(REGISTER, json=payload())

    assert "password" not in response.text
    assert "$2b$" not in response.text


def test_a_duplicate_email_is_rejected(anon_client: TestClient) -> None:
    anon_client.post(REGISTER, json=payload())

    response = anon_client.post(
        REGISTER, json=payload(display_name="Someone Else")
    )

    assert response.status_code == 409
    assert "email" in response.json()["error"]["message"].lower()


def test_an_email_differing_only_in_case_is_the_same_account(
    anon_client: TestClient,
) -> None:
    anon_client.post(REGISTER, json=payload())

    response = anon_client.post(
        REGISTER, json=payload(email="ALICE@Example.com", display_name="Other")
    )

    assert response.status_code == 409


def test_a_duplicate_display_name_is_rejected(anon_client: TestClient) -> None:
    anon_client.post(REGISTER, json=payload())

    response = anon_client.post(
        REGISTER, json=payload(email="other@example.com")
    )

    assert response.status_code == 409
    assert "display name" in response.json()["error"]["message"].lower()


@pytest.mark.parametrize(
    "bad_email", ["not-an-email", "@example.com", "alice@", "alice example.com", ""]
)
def test_an_invalid_email_is_rejected(anon_client: TestClient, bad_email: str) -> None:
    response = anon_client.post(REGISTER, json=payload(email=bad_email))

    assert response.status_code == 422


def test_a_short_password_is_rejected(anon_client: TestClient) -> None:
    response = anon_client.post(REGISTER, json=payload(password="short"))

    assert response.status_code == 422
    assert "8" in response.json()["error"]["message"]


def test_an_empty_display_name_is_rejected(anon_client: TestClient) -> None:
    response = anon_client.post(REGISTER, json=payload(display_name="   "))

    assert response.status_code == 422


def test_a_failed_registration_leaves_nothing_behind(
    anon_client: TestClient, db_session: Session
) -> None:
    """A half-registered learner — a user with no stats — would break every
    screen, so registration is one transaction."""
    before = db_session.scalar(select(User).where(User.email == "alice@example.com"))
    assert before is None

    anon_client.post(REGISTER, json=payload(password="tiny"))

    assert (
        db_session.scalar(select(User).where(User.email == "alice@example.com"))
        is None
    )


# --------------------------------------------------------------------------
# Login
# --------------------------------------------------------------------------


def test_valid_credentials_start_a_session(
    anon_client: TestClient, db_session: Session
) -> None:
    settings = get_settings()

    response = anon_client.post(
        LOGIN,
        json={
            "email": settings.demo_email,
            "password": settings.demo_user_password,
        },
    )

    assert response.status_code == 200
    assert settings.session_cookie_name in response.cookies
    assert db_session.scalar(select(SessionRow)) is not None


def test_the_session_cookie_is_httponly_and_samesite(
    anon_client: TestClient,
) -> None:
    """The flags are the security, so they are asserted rather than assumed."""
    settings = get_settings()

    response = anon_client.post(
        LOGIN,
        json={
            "email": settings.demo_email,
            "password": settings.demo_user_password,
        },
    )

    header = response.headers["set-cookie"].lower()
    # HttpOnly is why the token can never reach localStorage or a script.
    assert "httponly" in header
    assert "samesite=lax" in header


def test_the_session_token_is_not_stored_in_plaintext(
    anon_client: TestClient, db_session: Session
) -> None:
    settings = get_settings()
    response = anon_client.post(
        LOGIN,
        json={
            "email": settings.demo_email,
            "password": settings.demo_user_password,
        },
    )
    token = response.cookies[settings.session_cookie_name]

    stored = db_session.scalar(select(SessionRow.id))

    # A database copy contains no usable session.
    assert stored != token
    assert len(stored) == 64  # sha256 hex


def test_a_wrong_password_is_rejected(anon_client: TestClient) -> None:
    response = anon_client.post(
        LOGIN,
        json={"email": get_settings().demo_email, "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_an_unknown_email_and_a_wrong_password_are_indistinguishable(
    anon_client: TestClient,
) -> None:
    """Different messages here would turn the login form into an account
    directory: submit an address, learn whether it is registered."""
    unknown = anon_client.post(
        LOGIN, json={"email": "nobody@example.com", "password": "password123"}
    )
    wrong = anon_client.post(
        LOGIN, json={"email": get_settings().demo_email, "password": "nope12345"}
    )

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


def test_a_failed_login_creates_no_session(
    anon_client: TestClient, db_session: Session
) -> None:
    anon_client.post(
        LOGIN, json={"email": "nobody@example.com", "password": "password123"}
    )

    assert db_session.scalar(select(SessionRow)) is None


# --------------------------------------------------------------------------
# Current user
# --------------------------------------------------------------------------


def test_me_returns_the_session_owner(client: TestClient) -> None:
    body = client.get(ME).json()

    assert body["user"]["username"] == get_settings().demo_username


def test_me_is_401_without_a_session(anon_client: TestClient) -> None:
    response = anon_client.get(ME)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_learner_endpoints_are_401_without_a_session(
    anon_client: TestClient,
) -> None:
    """Identity is required everywhere it is used, not just on /auth/me."""
    for path in (
        "/api/v1/users/me",
        "/api/v1/users/me/stats",
        "/api/v1/users/me/profile",
        "/api/v1/users/me/achievements",
        "/api/v1/leaderboard",
        "/api/v1/courses/1/path",
    ):
        assert anon_client.get(path).status_code == 401, path

    assert anon_client.post("/api/v1/lessons/1/start").status_code == 401


def test_a_garbage_cookie_does_not_authenticate(anon_client: TestClient) -> None:
    anon_client.cookies.set(get_settings().session_cookie_name, "not-a-real-token")

    assert anon_client.get(ME).status_code == 401


def test_an_expired_session_does_not_authenticate(
    client: TestClient, db_session: Session
) -> None:
    session = db_session.scalar(select(SessionRow))
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    response = client.get(ME)

    assert response.status_code == 401
    # The stale row is cleaned up on sight, so the table does not grow forever.
    assert db_session.get(SessionRow, session.id) is None


# --------------------------------------------------------------------------
# Logout
# --------------------------------------------------------------------------


def test_logout_invalidates_the_session_server_side(
    client: TestClient, db_session: Session
) -> None:
    """Clearing the cookie alone would leave a working key lying around."""
    assert db_session.scalar(select(SessionRow)) is not None

    response = client.post(LOGOUT)

    assert response.status_code == 200
    assert response.json()["ended"] is True
    assert db_session.scalar(select(SessionRow)) is None


def test_after_logout_learner_data_is_unreachable(client: TestClient) -> None:
    client.post(LOGOUT)

    assert client.get("/api/v1/users/me/stats").status_code == 401


def test_logging_out_twice_is_not_an_error(client: TestClient) -> None:
    client.post(LOGOUT)

    response = client.post(LOGOUT)

    assert response.status_code == 200
    assert response.json()["ended"] is False


def test_logout_does_not_end_another_browsers_session(
    client: TestClient, anon_client: TestClient, db_session: Session
) -> None:
    """Signing out on a laptop must not sign you out on a phone."""
    settings = get_settings()
    anon_client.post(
        LOGIN,
        json={
            "email": settings.demo_email,
            "password": settings.demo_user_password,
        },
    )
    assert len(db_session.scalars(select(SessionRow)).all()) == 2

    client.post(LOGOUT)

    assert anon_client.get(ME).status_code == 200
    assert len(db_session.scalars(select(SessionRow)).all()) == 1
