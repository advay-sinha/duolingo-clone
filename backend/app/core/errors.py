"""Application-level errors, and how they become HTTP responses.

**Why not just raise ``HTTPException`` from the service layer?** Because a
service is supposed to be callable from anywhere — a test, a CLI command, a
future background job — and none of those speak HTTP. A service that raises
``HTTPException`` has quietly become part of the web layer, and testing it means
importing FastAPI.

So services raise plain domain errors that describe *what went wrong in the
domain*, and one handler registered in ``main.py`` decides what status code that
deserves. The mapping lives in exactly one place.

**The envelope.** Every error body is ``{"error": {"code", "message"}}``. That
was only true of domain errors until Phase 8 — FastAPI's own validation failures
returned ``{"detail": [...]}`` with pydantic internals, and an unmatched route
returned ``{"detail": "Not Found"}``, so the frontend actually had three shapes
to deal with and dealt with none of them. ``main.py`` now registers handlers for
``RequestValidationError`` and ``StarletteHTTPException`` too, which is what
makes the single-shape claim above true rather than aspirational.
"""


class DomainError(Exception):
    """Base class for expected, meaningful failures.

    ``status_code`` and ``code`` are class attributes so a subclass declares its
    own HTTP meaning once, and the handler stays a single generic function.
    """

    status_code: int = 400
    code: str = "domain_error"

    #: Extra HTTP headers this error should carry. Almost always empty — the
    #: envelope is the response — but `Retry-After` on a 429 is genuinely part of
    #: the answer rather than part of the message, and a header is where a client
    #: looks for it.
    headers: dict[str, str] | None = None

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    """A requested resource does not exist.

    Used by the path endpoint for an unknown course id. Returning 404 rather
    than an empty 200 payload matters: an empty path and a nonexistent course
    are different situations, and a client that cannot tell them apart will
    render "you have finished everything" for a typo in a URL.
    """

    status_code = 404
    code = "not_found"


class ForbiddenError(DomainError):
    """The caller is authenticated but not entitled to this resource.

    Used when an attempt belongs to a different learner. 403 rather than 404
    because the resource exists — and because in a single-learner demo, hiding
    that fact buys nothing.
    """

    status_code = 403
    code = "forbidden"


class ConflictError(DomainError):
    """The request is well-formed but the resource's state forbids it.

    Covers every "you cannot do that *right now*" case in the lesson engine:
    submitting an answer with no hearts left, answering into a finished attempt,
    completing an attempt twice, or completing one with unanswered exercises.
    409 rather than 400 because nothing is wrong with the request itself — the
    same request would have succeeded a moment earlier, or will succeed once the
    state changes.
    """

    status_code = 409
    code = "conflict"


class RateLimitedError(DomainError):
    """Too many failed attempts from this caller. 429.

    429 rather than reusing the 401, and the distinction is worth defending:
    401 means "those credentials are wrong", and repeating it here would tell a
    learner who mistyped their password five times that their sixth *correct*
    attempt was also wrong. 429 says what actually happened and, with
    ``Retry-After``, when to come back.

    **It leaks nothing about whether an email exists**, which is the property the
    login endpoint is built around. The limiter counts failures against
    ``(email, IP)`` without ever consulting the users table, so an unknown address
    and a known one are blocked after exactly the same number of attempts, with
    exactly the same response.
    """

    status_code = 429
    code = "rate_limited"


class DemoUserMissingError(DomainError):
    """The seeded learner is absent, so no request can be attributed.

    **Unused since Phase 9** and kept only so the historical reasoning survives:
    503 rather than 404 or 500 on purpose, because the API was correctly built
    but its data was not there yet — an operator problem with a known fix, and
    the message named it.

    Identity now comes from a session cookie, so the failure mode it described no
    longer exists: an unauthenticated request is a 401 from
    ``auth_service.AuthenticationError``, not a missing-seed 503.
    """

    status_code = 503
    code = "demo_user_missing"
