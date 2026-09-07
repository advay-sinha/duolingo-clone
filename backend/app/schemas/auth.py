"""API schemas for authentication.

**The security-critical property here mirrors `schemas/lesson.py`:** no response
model declares ``password`` or ``password_hash``, so neither can be serialised
even by a future edit that forgets. The request models are the only place a
password appears, and it travels in one direction — inward.

``AuthenticatedUser`` carries ``email`` because it describes *the caller to
themselves*. ``LeaderboardEntry``, which describes one learner to another, does
not — and that separation is the point of having two models rather than one
``UserResponse`` used everywhere.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    """`POST /auth/register`.

    Field-level rules are intentionally minimal here; the real validation lives
    in ``auth_service.validate_registration`` so it is testable without HTTP and
    reads as one list of rules rather than being split between a schema and a
    service.
    """

    email: str = Field(max_length=255, examples=["alex@example.com"])
    password: str = Field(max_length=200, examples=["correct horse battery"])
    display_name: str = Field(max_length=80, examples=["Alex"])


class LoginRequest(BaseModel):
    """`POST /auth/login`."""

    email: str = Field(max_length=255)
    password: str = Field(max_length=200)


class AuthenticatedUser(BaseModel):
    """The caller, as described to themselves.

    Includes ``email`` — this is the one response in the API that does, because
    it is the only one that describes the caller rather than a third party.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    display_name: str
    avatar_url: str
    created_at: datetime


class AuthResponse(BaseModel):
    """`POST /auth/register`, `POST /auth/login`, `GET /auth/me`.

    One shape for all three, so the frontend has a single thing to parse and the
    "who am I" question always has the same answer regardless of how the session
    began. The session token is **not** in the body: it is set as an HttpOnly
    cookie, which is exactly what keeps JavaScript — including any script that
    manages to run on the page — from reading it.
    """

    user: AuthenticatedUser


class LogoutResponse(BaseModel):
    """`POST /auth/logout`."""

    #: Reports whether a session was actually invalidated. Logging out twice is
    #: not an error — it is the same end state — so this is informational rather
    #: than a reason to return a failure status.
    ended: bool
