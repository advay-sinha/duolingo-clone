"""Heart regeneration.

Split in two: the pure rule (no database, no clock) and its application through
the service and the API. Every time-based test injects an explicit `now` — there
is **no `sleep()` anywhere**, so the whole suite runs in milliseconds and the
boundaries are exact rather than approximate.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, UserStats
from app.services import user_service
from app.services.gamification import as_utc, regenerate_hearts

T0 = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
MAX = 5
INTERVAL = 30


def regen(hearts: int, minutes: float, *, updated: datetime = T0):
    return regenerate_hearts(
        hearts=hearts,
        hearts_updated_at=updated,
        now=updated + timedelta(minutes=minutes),
        max_hearts=MAX,
        interval_minutes=INTERVAL,
    )


# --------------------------------------------------------------------------
# The pure rule
# --------------------------------------------------------------------------


def test_full_hearts_stay_full() -> None:
    result = regen(5, 120)
    assert result.hearts == 5


def test_time_at_full_hearts_does_not_bank_credit() -> None:
    """The timestamp is normalised while full.

    Otherwise a learner idle for a day would lose a heart and instantly get it
    back, because the stale timestamp had banked 48 intervals.
    """
    result = regen(5, 1440)
    assert result.updated_at == T0 + timedelta(minutes=1440)


def test_just_under_the_interval_does_not_regenerate() -> None:
    result = regen(4, 29)
    assert result.hearts == 4
    assert result.changed is False
    assert result.updated_at == T0


def test_exactly_one_interval_grants_one_heart() -> None:
    result = regen(4, 30)
    assert result.hearts == 5


def test_two_intervals_grant_two_hearts() -> None:
    result = regen(2, 60)
    assert result.hearts == 4


def test_zero_hearts_recovers_fully_after_enough_time() -> None:
    result = regen(0, 150)
    assert result.hearts == 5


def test_regeneration_is_capped_at_the_maximum() -> None:
    result = regen(0, 10_000)
    assert result.hearts == MAX


def test_the_partial_interval_carries_forward() -> None:
    """The subtle one.

    At 45 minutes the learner earns one heart and is 15 minutes into the next.
    If the timestamp were set to `now`, those 15 minutes would be thrown away —
    and a learner reading their stats every 29 minutes would never regenerate
    at all.
    """
    result = regen(2, 45)

    assert result.hearts == 3
    # Advanced by one whole interval, not to `now`.
    assert result.updated_at == T0 + timedelta(minutes=30)


def test_re_reading_does_not_grant_the_same_interval_twice() -> None:
    first = regen(2, 45)
    second = regenerate_hearts(
        hearts=first.hearts,
        hearts_updated_at=first.updated_at,
        now=T0 + timedelta(minutes=45),
        max_hearts=MAX,
        interval_minutes=INTERVAL,
    )

    assert second.hearts == first.hearts
    assert second.changed is False


def test_reaching_full_normalises_the_timestamp_to_now() -> None:
    result = regen(4, 95)
    assert result.hearts == 5
    assert result.updated_at == T0 + timedelta(minutes=95)


def test_a_backwards_clock_changes_nothing() -> None:
    result = regenerate_hearts(
        hearts=3,
        hearts_updated_at=T0,
        now=T0 - timedelta(hours=1),
        max_hearts=MAX,
        interval_minutes=INTERVAL,
    )
    assert result.hearts == 3
    assert result.changed is False


def test_as_utc_attaches_utc_to_a_naive_timestamp() -> None:
    """SQLite returns naive datetimes; subtracting one from an aware `now`
    raises. This is the guard that stops every heart read being a 500."""
    naive = datetime(2026, 3, 15, 12, 0)

    assert as_utc(naive).tzinfo is timezone.utc
    assert as_utc(T0) is T0


# --------------------------------------------------------------------------
# Through the service and the database
# --------------------------------------------------------------------------


def test_the_service_persists_regenerated_hearts(db_session: Session) -> None:
    user = db_session.scalar(select(User))
    stats = db_session.get(UserStats, user.id)
    stats.hearts = 1
    stats.hearts_updated_at = datetime.now(timezone.utc) - timedelta(minutes=61)
    db_session.commit()

    result = user_service.current_stats(db_session, user)

    assert result.hearts == 3
    db_session.expire_all()
    assert db_session.get(UserStats, user.id).hearts == 3


def test_regeneration_leaves_xp_streak_and_crowns_alone(db_session: Session) -> None:
    """Regeneration touches hearts and its timestamp. Nothing else."""
    user = db_session.scalar(select(User))
    stats = db_session.get(UserStats, user.id)
    stats.hearts = 0
    stats.total_xp = 250
    stats.current_streak = 4
    stats.longest_streak = 9
    stats.daily_xp = 30
    stats.hearts_updated_at = datetime.now(timezone.utc) - timedelta(hours=3)
    db_session.commit()

    result = user_service.current_stats(db_session, user)

    assert result.hearts == 5
    assert result.total_xp == 250
    assert result.current_streak == 4
    assert result.longest_streak == 9
    assert result.daily_xp == 30


def test_an_unchanged_read_writes_nothing(db_session: Session) -> None:
    user = db_session.scalar(select(User))
    stats = db_session.get(UserStats, user.id)
    stats.hearts = 3
    original = datetime.now(timezone.utc) - timedelta(minutes=5)
    stats.hearts_updated_at = original
    db_session.commit()

    user_service.current_stats(db_session, user)

    db_session.expire_all()
    after = db_session.get(UserStats, user.id)
    assert after.hearts == 3
    assert as_utc(after.hearts_updated_at) == as_utc(original)


# --------------------------------------------------------------------------
# Through the API — the recovery path
# --------------------------------------------------------------------------


def test_stats_endpoint_reflects_regenerated_hearts(
    client: TestClient, db_session: Session
) -> None:
    user = db_session.scalar(select(User))
    stats = db_session.get(UserStats, user.id)
    stats.hearts = 0
    stats.hearts_updated_at = datetime.now(timezone.utc) - timedelta(minutes=31)
    db_session.commit()

    body = client.get("/api/v1/users/me/stats").json()

    assert body["hearts"] == 1


def test_zero_hearts_still_blocks_a_lesson_before_the_interval(
    client: TestClient, db_session: Session
) -> None:
    user = db_session.scalar(select(User))
    stats = db_session.get(UserStats, user.id)
    stats.hearts = 0
    stats.hearts_updated_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db_session.commit()

    assert client.post("/api/v1/lessons/1/start").status_code == 409


def test_starting_a_lesson_applies_regeneration(
    client: TestClient, db_session: Session
) -> None:
    """The recovery path: waiting out the interval is enough to play again,
    without having to load the stats screen first."""
    user = db_session.scalar(select(User))
    stats = db_session.get(UserStats, user.id)
    stats.hearts = 0
    stats.hearts_updated_at = datetime.now(timezone.utc) - timedelta(minutes=31)
    db_session.commit()

    response = client.post("/api/v1/lessons/1/start")

    assert response.status_code == 200
    assert response.json()["hearts"] == 1


def test_a_failed_regeneration_write_leaves_hearts_untouched(
    db_session: Session, monkeypatch
) -> None:
    """Transaction safety: if the commit fails, the old heart state stands."""
    user = db_session.scalar(select(User))
    stats = db_session.get(UserStats, user.id)
    stats.hearts = 1
    stats.hearts_updated_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db_session.commit()

    def explode():
        raise RuntimeError("commit failed")

    monkeypatch.setattr(db_session, "commit", explode)

    with pytest.raises(RuntimeError):
        user_service.current_stats(db_session, user)

    monkeypatch.undo()
    db_session.expire_all()
    assert db_session.get(UserStats, user.id).hearts == 1
