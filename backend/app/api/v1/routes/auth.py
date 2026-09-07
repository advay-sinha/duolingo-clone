"""Authentication routes: register, login, logout, me.

**This is the only module in the backend that knows a cookie exists.** Services
take and return a ``User`` and a token string; the translation between "a token"
and "a ``Set-Cookie`` header" happens here and nowhere else. That is the same
boundary discipline the rest of the codebase uses for HTTP status codes — the
service raises meaning, the edge speaks protocol.
"""

from fastapi import APIRouter, Request, Response

from app.api.v1.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.schemas.auth import (
    AuthResponse,
    AuthenticatedUser,
    LoginRequest,
    LogoutResponse,
    RegisterRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    """Attach the session cookie.

    Every flag here is load-bearing:

    * ``httponly`` — JavaScript cannot read the cookie. This is why the token is
      not in the response body and never reaches ``localStorage``: a script that
      manages to run on the page can still *make* requests, but it cannot read
      the credential and send it somewhere else.
    * ``samesite="lax"`` — the browser will not attach this cookie to a
      cross-site POST, which is what a CSRF attack needs. "Lax" rather than
      "strict" so that following an ordinary link into the app keeps you logged
      in.
    * ``secure`` — configuration, not a literal. Off for local http, and it must
      be on for any https deployment or the cookie travels in the clear.
    * ``path="/"`` — the API is versioned under a prefix, but the cookie must be
      sent for every route under it.
    """
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_lifetime_days * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=201,
    summary="Create an account and log in",
    responses={
        409: {"description": "Email or display name already taken"},
        422: {"description": "A field is unusable"},
    },
)
def register(
    payload: RegisterRequest, response: Response, db: DbSession
) -> AuthResponse:
    """Register a learner and start their session immediately.

    A new account is logged in as part of registering — asking someone to type
    the credentials they just chose, a second time, is friction with no security
    benefit.
    """
    user, token = auth_service.register(
        db,
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
    )
    _set_session_cookie(response, token)
    return AuthResponse(user=AuthenticatedUser.model_validate(user))


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Log in with email and password",
    responses={401: {"description": "Email or password is incorrect"}},
)
def login(payload: LoginRequest, response: Response, db: DbSession) -> AuthResponse:
    """Verify credentials and start a session.

    Both failure modes — unknown email, wrong password — return the same 401 and
    the same message. See ``auth_service.login`` for why.
    """
    user, token = auth_service.login(
        db, email=payload.email, password=payload.password
    )
    _set_session_cookie(response, token)
    return AuthResponse(user=AuthenticatedUser.model_validate(user))


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="End the current session",
)
def logout(request: Request, response: Response, db: DbSession) -> LogoutResponse:
    """Invalidate this browser's session and clear its cookie.

    **The server row is deleted, not just the cookie.** Clearing the cookie alone
    would leave a valid session behind that anyone holding a copy of the token
    could keep using — which is the difference between logging out and hiding the
    key.

    Deliberately does not require an authenticated caller: logging out with an
    already-expired session should succeed quietly, not fail with a 401.
    """
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    ended = auth_service.destroy_session(db, token)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return LogoutResponse(ended=ended)


@router.get(
    "/me",
    response_model=AuthResponse,
    summary="The currently authenticated learner",
    responses={401: {"description": "Not signed in"}},
)
def me(user: CurrentUser) -> AuthResponse:
    """Who the session belongs to.

    The frontend calls this to decide whether to show the app or redirect to the
    login page, rather than keeping an "is logged in" flag of its own. The server
    stays the source of truth, so a session that expired mid-visit is discovered
    on the next request instead of being believed until reload.
    """
    return AuthResponse(user=AuthenticatedUser.model_validate(user))
