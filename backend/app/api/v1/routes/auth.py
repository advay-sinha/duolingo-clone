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
from app.core.errors import RateLimitedError
from app.core.rate_limit import RateLimiter, login_key
from app.schemas.auth import (
    AuthResponse,
    AuthenticatedUser,
    LoginRequest,
    LogoutResponse,
    RegisterRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

#: Failed-login counter, shared by every request in this process.
#:
#: Built once at import so its state survives between requests — which is the
#: entire point, and also its limitation: the state lives in *this* process. See
#: `app/core/rate_limit.py` for what that means for a multi-instance deployment.
login_limiter = RateLimiter(
    max_attempts=get_settings().login_max_attempts,
    window_seconds=get_settings().login_window_seconds,
)


def client_ip(request: Request) -> str | None:
    """Identify the caller's network address.

    `X-Forwarded-For` is read **only** when `TRUST_PROXY_HEADERS` is on, and that
    condition is load-bearing. The header is set by the client unless a proxy
    overwrites it, so trusting it with nothing in front means an attacker sends a
    different value on every request and the rate limit counts each one as a new
    caller — a limiter that cannot limit. Behind a real proxy the opposite is
    true: without it, every request appears to come from the proxy and one bucket
    is shared by everybody.

    The first entry is taken because a proxy chain appends, so the leftmost value
    is the original client.
    """
    if get_settings().trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


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
    responses={
        401: {"description": "Email or password is incorrect"},
        429: {"description": "Too many failed attempts; see the Retry-After header"},
    },
)
def login(
    payload: LoginRequest, request: Request, response: Response, db: DbSession
) -> AuthResponse:
    """Verify credentials and start a session.

    Both failure modes — unknown email, wrong password — return the same 401 and
    the same message. See ``auth_service.login`` for why.

    **Rate limiting lives here rather than in the service**, and that placement is
    deliberate: how often a caller may try is a property of the transport, not of
    the domain. `auth_service.login` still knows nothing about HTTP, IP addresses
    or request counts, so it stays callable from a test or a CLI without any of
    this being in the way.

    **The check runs before the password is verified.** That is not an
    optimisation — bcrypt at cost 12 takes roughly a quarter-second, so a login
    endpoint that hashes before checking the limit is a way to spend the server's
    CPU as fast as requests can be sent. Refusing first makes a blocked attempt
    nearly free to reject.

    Only *failures* count, and a success clears the key, so a learner who signs in
    correctly is never limited.
    """
    key = login_key(payload.email, client_ip(request))

    if login_limiter.is_blocked(key):
        error = RateLimitedError(
            "Too many failed sign-in attempts. Please wait and try again."
        )
        error.headers = {"Retry-After": str(login_limiter.retry_after(key))}
        raise error

    try:
        user, token = auth_service.login(
            db, email=payload.email, password=payload.password
        )
    except auth_service.AuthenticationError:
        login_limiter.register_failure(key)
        # Re-raised unchanged: the response a caller sees below the limit is
        # byte-for-byte what it was before Phase 10.
        raise

    login_limiter.reset(key)
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
