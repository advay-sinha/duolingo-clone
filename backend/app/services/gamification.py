"""Gamification rules — XP, hearts, streaks — as pure functions.

Like ``grading.py``, everything here is pure: given the current state and the
inputs, it returns the new state. No database, no session, no HTTP, and — the
important one — **no calls to ``date.today()``**. The current date is passed in.

That last point matters more than it looks. A streak rule that reads the clock
internally can only be tested by waiting a day or by monkey-patching time. One
that takes ``today`` as an argument can be tested across a month of scenarios in
milliseconds, which is why every streak branch below has a test.

**The date basis is UTC**, applied consistently. Per-learner timezones are real
Duolingo behaviour and real complexity (a streak that depends on where you were
standing at midnight); the assignment does not need them, and mixing bases would
be worse than picking one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone


@dataclass(frozen=True)
class StreakUpdate:
    """The result of applying the streak rule."""

    current_streak: int
    longest_streak: int
    #: True when this activity extended or started a streak (i.e. first activity
    #: of a new day), as opposed to being a second lesson on the same day.
    extended: bool


def apply_streak(
    *,
    current_streak: int,
    longest_streak: int,
    last_activity_date: date | None,
    today: date,
) -> StreakUpdate:
    """Apply the daily streak rule.

    The four cases, stated exhaustively:

    * **First ever activity** (``last_activity_date is None``) -> streak becomes 1.
    * **Same-day activity** (``last == today``) -> unchanged. A learner doing five
      lessons in one day has a streak of 1, not 5.
    * **Next-day activity** (``last == today - 1 day``) -> streak increments.
    * **Missed one or more days** (``last < today - 1 day``) -> streak resets to 1,
      not to 0: today's activity is itself day one of a new streak.

    ``longest_streak`` only ever rises, so a broken streak does not erase the
    learner's record.

    A ``last_activity_date`` in the future is treated as "same day or later" and
    leaves the streak untouched — it can only arise from a clock change, and the
    safe response is to leave the learner's record alone rather than reset it.
    """
    if last_activity_date is None:
        return StreakUpdate(1, max(longest_streak, 1), extended=True)

    if last_activity_date >= today:
        return StreakUpdate(current_streak, longest_streak, extended=False)

    if last_activity_date == today - timedelta(days=1):
        new_streak = current_streak + 1
        return StreakUpdate(new_streak, max(longest_streak, new_streak), extended=True)

    return StreakUpdate(1, max(longest_streak, 1), extended=True)


def daily_xp_after(
    *,
    daily_xp: int,
    last_activity_date: date | None,
    today: date,
    earned: int,
) -> int:
    """Return today's XP total, rolling over at a date change.

    ``daily_xp`` is progress toward the daily goal, so it must reset when the day
    does. There is no scheduled job to do that: the value is re-derived whenever
    activity happens, by comparing the stored activity date to today. Yesterday's
    total is simply not carried forward.
    """
    if last_activity_date is None or last_activity_date != today:
        return earned
    return daily_xp + earned


def hearts_after_mistake(*, hearts: int, cost: int) -> int:
    """Deduct hearts for a wrong answer, floored at zero.

    ``max(0, ...)`` in application code *and* a ``CHECK (hearts >= 0)`` in the
    schema. Belt and braces on purpose: the check constraint is the guarantee,
    this is the graceful behaviour that keeps the constraint from ever firing.
    """
    return max(0, hearts - cost)


def as_utc(value: datetime) -> datetime:
    """Interpret a stored timestamp as UTC.

    **Why this exists.** ``user_stats.hearts_updated_at`` is written as a
    timezone-aware UTC datetime, but the column is a plain ``DateTime`` and
    SQLite has no timezone type — so it reads back **naive**. Subtracting a naive
    datetime from ``datetime.now(timezone.utc)`` raises ``TypeError``, which
    would turn every heart read into a 500.

    Everything this application writes is UTC, so attaching UTC to a naive value
    is correct rather than a guess. Doing it in one named function means the
    assumption is stated once instead of being re-derived at each call site.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class HeartRegen:
    """The result of applying lazy heart regeneration."""

    hearts: int
    #: The new ``hearts_updated_at`` to persist.
    updated_at: datetime
    #: True when hearts actually changed, so callers can skip a pointless write.
    changed: bool


def regenerate_hearts(
    *,
    hearts: int,
    hearts_updated_at: datetime,
    now: datetime,
    max_hearts: int,
    interval_minutes: int,
) -> HeartRegen:
    """Refill hearts for the time that has passed, lazily.

    **Why lazy rather than scheduled.** A background job would need a scheduler,
    a worker process and a way to run it in every environment, all to compute a
    value that is a pure function of two timestamps. Deriving it on read costs
    nothing, cannot drift, and works identically in a test, in a request and
    after the server has been switched off for a week.

    The rule: one heart per ``interval_minutes`` elapsed, capped at
    ``max_hearts``.

    **The timestamp is the subtle part.** Two wrong answers are tempting and both
    break the feature:

    * Leaving ``hearts_updated_at`` alone would re-grant the same intervals on
      every read — hearts would refill instantly on the second call.
    * Setting it to ``now`` whenever anything regenerates would *discard the
      partial interval*. A learner read at 29 minutes, then again at 31, would
      have their progress reset twice and never regenerate at all.

    So the timestamp advances by **whole intervals consumed**, leaving the
    remainder to carry forward. At full hearts it is normalised to ``now``,
    because there is nothing left to accumulate toward and a stale timestamp
    would otherwise bank credit for a heart the learner has not spent yet.

    Both datetimes must be timezone-aware UTC — use `as_utc` on stored values.
    """
    if hearts >= max_hearts:
        # Already full. Normalise the timestamp so that time spent at full does
        # not bank intervals toward the next heart lost.
        return HeartRegen(hearts, now, changed=hearts_updated_at != now)

    elapsed = now - hearts_updated_at
    if elapsed < timedelta(0):
        # A clock change moved time backwards. Do nothing rather than punish or
        # reward the learner for it.
        return HeartRegen(hearts, hearts_updated_at, changed=False)

    interval = timedelta(minutes=interval_minutes)
    intervals = int(elapsed // interval)
    if intervals <= 0:
        return HeartRegen(hearts, hearts_updated_at, changed=False)

    new_hearts = min(max_hearts, hearts + intervals)

    if new_hearts >= max_hearts:
        return HeartRegen(new_hearts, now, changed=True)

    # Consume only the intervals actually granted; the remainder carries forward.
    return HeartRegen(
        new_hearts, hearts_updated_at + interval * intervals, changed=True
    )


def crowns_for_skill(*, lessons_completed: int, total_lessons: int) -> int:
    """Award a crown once every lesson in the skill has been completed.

    One crown per skill in this MVP. Real Duolingo has multiple crown levels per
    skill; that needs a repeat-practice loop the assignment does not require, and
    the schema already has an integer column ready if it is ever added.

    Returns 0 for a skill with no lessons, rather than treating "nothing to do"
    as "finished" — an empty skill should not silently unlock the next one.
    """
    if total_lessons <= 0:
        return 0
    return 1 if lessons_completed >= total_lessons else 0
