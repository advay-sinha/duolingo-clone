"""A fixed-window rate limiter for failed logins.

**What this is for.** Through Phase 9 the login endpoint would accept unlimited
attempts. Two things make that worse than it sounds: bcrypt at cost 12 takes
roughly a quarter-second, so the endpoint is also an cheap way to burn the
server's CPU; and an unlimited guess budget is what turns a leaked password list
into a working credential-stuffing attack.

**What this is not.** It is a mitigation, not an identity-security system. It
raises the cost of guessing; it does not make guessing impossible, and it is not
a substitute for the things a real deployment would have — a password policy that
rejects known-breached passwords, multi-factor authentication, anomaly detection,
and an account-lockout flow with a way back in. Those are deliberately out of
scope (see the scope note at the top of ``auth_service``), and this closes the
one gap that was cheap to close.

Three design decisions, each with a rejected alternative:

**Fixed window, not a sliding log.** A sliding window would need a timestamp per
attempt and pruning on every check. A fixed window needs two numbers per key. The
known weakness of fixed windows — a burst at the boundary can span two windows —
means an attacker gets at most ``2 × MAX`` attempts in a window's width instead of
``MAX``. At these magnitudes that changes nothing that matters.

**In memory, not Redis.** The brief rules out Redis and it would be the wrong
call anyway: this is a single-process monolith, and a network hop plus an
operational dependency to count to five is not a trade worth making.
**KNOWN LIMITATION, and it is a real one:** the counters live in this process's
memory. They are lost on restart, and on a multi-instance or serverless
deployment each instance counts separately — so N instances multiply the
effective limit by N. On the persistent single-container deployment this project
targets, that is exactly one instance and the limit is the limit. If this ever
runs behind an autoscaler, the honest fix is the platform's own rate limiting or
a shared store, and this module should be deleted rather than patched.

**Counting failures only.** A successful login clears the key. Someone who signs
in correctly forty times in a row is a person with a flaky network or several
devices, not an attacker, and locking them out would be the limiter causing the
outage it exists to prevent.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class _Window:
    """One key's current window: when it started, and how many failures in it."""

    started_at: float
    failures: int = 0


@dataclass
class RateLimiter:
    """Counts failures per key inside a fixed time window.

    Args:
        max_attempts: Failures allowed per window before the key is blocked.
        window_seconds: How wide the window is.
        clock: Returns a monotonically increasing number of seconds.
            **Injected on purpose** — it is what lets the tests prove expiry
            without sleeping, and what keeps them fast and deterministic. The
            default is ``time.monotonic``, not ``time.time``, because the limiter
            must not be confused by a clock adjustment or a daylight-saving
            change.
    """

    max_attempts: int
    window_seconds: float
    clock: Callable[[], float] = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.clock is None:
            import time

            self.clock = time.monotonic
        self._windows: dict[str, _Window] = {}
        # Uvicorn runs synchronous endpoints in a threadpool, so two requests can
        # reach `register_failure` at the same time. Without the lock, two
        # failures could read the same count and both write count+1 — losing one,
        # which is the wrong direction to be wrong in for a security control.
        self._lock = threading.Lock()

    # ----------------------------------------------------------------- query

    def is_blocked(self, key: str) -> bool:
        """Whether this key has used up its budget.

        Expiry is evaluated here rather than swept by a background job — the same
        pattern as session expiry and heart regeneration. A stale window simply
        stops counting; nothing has to run for the rule to be correct.
        """
        with self._lock:
            window = self._current_window(key)
            return window is not None and window.failures >= self.max_attempts

    def retry_after(self, key: str) -> int:
        """Whole seconds until this key's window resets. Zero if not blocked."""
        with self._lock:
            window = self._current_window(key)
            if window is None or window.failures < self.max_attempts:
                return 0
            remaining = self.window_seconds - (self.clock() - window.started_at)
            return max(1, int(remaining + 0.999))

    # ----------------------------------------------------------------- update

    def register_failure(self, key: str) -> None:
        """Record one failed attempt, starting a new window if the old expired."""
        with self._lock:
            window = self._current_window(key)
            if window is None:
                window = _Window(started_at=self.clock())
                self._windows[key] = window
            window.failures += 1

    def reset(self, key: str) -> None:
        """Forget a key's failures. Called on a successful login."""
        with self._lock:
            self._windows.pop(key, None)

    def clear(self) -> None:
        """Forget everything. For tests, and for nothing else."""
        with self._lock:
            self._windows.clear()

    # ---------------------------------------------------------------- internal

    def _current_window(self, key: str) -> _Window | None:
        """This key's live window, dropping it if it has expired.

        Callers hold the lock. Expired entries are deleted on sight, which keeps
        the dictionary from growing without bound in normal use — the same
        housekeeping `resolve_session` does for expired session rows.
        """
        window = self._windows.get(key)
        if window is None:
            return None
        if self.clock() - window.started_at >= self.window_seconds:
            del self._windows[key]
            return None
        return window


def login_key(email: str, client_ip: str | None) -> str:
    """The key a login attempt is counted against.

    ``email + IP`` rather than either alone, and the choice matters:

    * **Email only** would let anyone lock a known user out of their own account
      by failing five logins against it — the limiter becomes the attack.
    * **IP only** would count a whole office or a mobile carrier's NAT as one
      client, so one person's typo budget is shared by hundreds.

    The pair means an attacker spraying one password across many accounts is
    limited per account, and a single user fumbling their password is limited to
    their own connection. It is not perfect — a botnet with an address per attempt
    defeats it — and the honest description is "raises the cost", not "prevents".

    The email is casefolded so ``Alex@x.com`` and ``alex@x.com`` share a budget,
    matching how the account itself is resolved.
    """
    return f"{email.strip().casefold()}|{client_ip or 'unknown'}"
