"""Shared route dependencies.

FastAPI's dependency injection means a route declares *what it needs* as a
parameter and the framework supplies it. Two things every data route needs: a
database session, and the current user.

Keeping them here rather than in each route file means they are defined once, and
— crucially for tests — they can be **overridden**. The API test suite swaps
``get_db`` for one bound to a throwaway database, and every route follows without
knowing anything changed.
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import User
from app.services import auth_service


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """Resolve the learner making this request, from their session cookie.

    **This is the change Phase 9 exists for.** Through Phase 8 this function
    returned the one seeded learner named by ``settings.demo_username``: there
    was no login, no session and no second user. It now reads the session cookie,
    looks up its row, and returns whoever it belongs to.

    Note how little else changed. Every route already depended on *"the current
    user"* rather than on *"the demo user"*, so adding real authentication
    touched this function and no route signature, no service, and no schema. That
    was the entire point of routing the assumption through one dependency in
    Phase 3, and it is the clearest payoff in the codebase for putting a boundary
    where a shortcut lives.

    The identity comes from the cookie and **never** from the request body or a
    query parameter. A client cannot ask to be someone else, because there is no
    field in which to ask.

    Raises:
        auth_service.AuthenticationError: no cookie, an unknown or expired
            session (401). The frontend turns that into a redirect to `/login`.
    """
    token = request.cookies.get(settings.session_cookie_name)
    user = auth_service.resolve_session(db, token)
    if user is None:
        raise auth_service.AuthenticationError("Sign in to continue.")
    return user


# Aliases so routes read as `db: DbSession` rather than repeating the full
# Annotated[...] spelling in every signature.
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
