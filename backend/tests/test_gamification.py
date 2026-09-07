"""Unit tests for the pure gamification rules.

`gamification.py` takes `today` as an argument rather than reading the clock,
which is what makes a month of streak scenarios testable in milliseconds instead
of requiring monkey-patched time.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.services.gamification import (
    apply_streak,
    crowns_for_skill,
    daily_xp_after,
    hearts_after_mistake,
)

TODAY = date(2026, 3, 15)
YESTERDAY = TODAY - timedelta(days=1)
LAST_WEEK = TODAY - timedelta(days=7)


# --------------------------------------------------------------------------
# Streaks — all four branches
# --------------------------------------------------------------------------


def test_first_ever_activity_starts_a_streak_of_one() -> None:
    result = apply_streak(
        current_streak=0, longest_streak=0, last_activity_date=None, today=TODAY
    )
    assert (result.current_streak, result.longest_streak) == (1, 1)
    assert result.extended is True


def test_a_second_lesson_on_the_same_day_does_not_extend_the_streak() -> None:
    """Five lessons in one day is a streak of 1, not 5."""
    result = apply_streak(
        current_streak=3, longest_streak=9, last_activity_date=TODAY, today=TODAY
    )
    assert (result.current_streak, result.longest_streak) == (3, 9)
    assert result.extended is False


def test_activity_the_next_day_increments_the_streak() -> None:
    result = apply_streak(
        current_streak=3, longest_streak=9, last_activity_date=YESTERDAY, today=TODAY
    )
    assert result.current_streak == 4
    assert result.extended is True


def test_a_missed_day_resets_the_streak_to_one_not_zero() -> None:
    """Today's activity is itself day one of a new streak."""
    result = apply_streak(
        current_streak=12, longest_streak=12, last_activity_date=LAST_WEEK, today=TODAY
    )
    assert result.current_streak == 1
    assert result.extended is True


def test_the_longest_streak_survives_a_reset() -> None:
    result = apply_streak(
        current_streak=12, longest_streak=12, last_activity_date=LAST_WEEK, today=TODAY
    )
    assert result.longest_streak == 12


def test_a_new_record_raises_the_longest_streak() -> None:
    result = apply_streak(
        current_streak=9, longest_streak=9, last_activity_date=YESTERDAY, today=TODAY
    )
    assert (result.current_streak, result.longest_streak) == (10, 10)


def test_a_future_activity_date_leaves_the_streak_untouched() -> None:
    """Only reachable via a clock change; the safe response is to do nothing."""
    tomorrow = TODAY + timedelta(days=1)
    result = apply_streak(
        current_streak=5, longest_streak=5, last_activity_date=tomorrow, today=TODAY
    )
    assert result.current_streak == 5
    assert result.extended is False


def test_a_streak_can_be_built_over_consecutive_days() -> None:
    streak, longest, last = 0, 0, None
    for offset in range(5):
        day = TODAY + timedelta(days=offset)
        result = apply_streak(
            current_streak=streak,
            longest_streak=longest,
            last_activity_date=last,
            today=day,
        )
        streak, longest, last = result.current_streak, result.longest_streak, day
    assert (streak, longest) == (5, 5)


# --------------------------------------------------------------------------
# Daily XP rollover
# --------------------------------------------------------------------------


def test_daily_xp_accumulates_within_one_day() -> None:
    assert (
        daily_xp_after(daily_xp=20, last_activity_date=TODAY, today=TODAY, earned=30)
        == 50
    )


def test_daily_xp_resets_on_a_new_day() -> None:
    """No scheduled job: the reset is derived from the stored activity date."""
    assert (
        daily_xp_after(
            daily_xp=200, last_activity_date=YESTERDAY, today=TODAY, earned=30
        )
        == 30
    )


def test_daily_xp_starts_fresh_for_a_new_learner() -> None:
    assert (
        daily_xp_after(daily_xp=0, last_activity_date=None, today=TODAY, earned=70)
        == 70
    )


# --------------------------------------------------------------------------
# Hearts
# --------------------------------------------------------------------------


def test_a_mistake_costs_one_heart() -> None:
    assert hearts_after_mistake(hearts=5, cost=1) == 4


def test_hearts_never_go_below_zero() -> None:
    assert hearts_after_mistake(hearts=0, cost=1) == 0
    assert hearts_after_mistake(hearts=1, cost=3) == 0


# --------------------------------------------------------------------------
# Crowns
# --------------------------------------------------------------------------


def test_no_crown_until_every_lesson_is_done() -> None:
    assert crowns_for_skill(lessons_completed=1, total_lessons=2) == 0


def test_a_crown_is_awarded_when_the_skill_is_finished() -> None:
    assert crowns_for_skill(lessons_completed=2, total_lessons=2) == 1


def test_a_crown_stays_at_one_even_if_the_count_overshoots() -> None:
    assert crowns_for_skill(lessons_completed=5, total_lessons=2) == 1


def test_an_empty_skill_earns_no_crown() -> None:
    """"Nothing to do" must not read as "finished", or it would unlock the next
    skill for free."""
    assert crowns_for_skill(lessons_completed=0, total_lessons=0) == 0
