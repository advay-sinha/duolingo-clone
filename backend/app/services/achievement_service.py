"""Achievement evaluation.

**Deliberately not a rules engine.** Six achievements, each a small predicate
over data the application already stores. A generic system with stored
conditions and an interpreter would be more code, harder to read, and would need
its own tests to prove the interpreter works — for six rules that fit on one
screen.

Every achievement here is evaluable from existing tables. Nothing was invented
to make one possible, and nothing is faked: an achievement the data cannot
support was simply not written.

Evaluation runs **inside the lesson-completion transaction**, so a learner can
never end up with a completed lesson whose achievement was lost, or an
achievement for a completion that rolled back.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Achievement,
    LessonAttempt,
    User,
    UserAchievement,
    UserSkillProgress,
    UserStats,
)

# Keys, mirrored in the seed. Kept as constants so a typo is an import error
# rather than a silently-never-awarded achievement.
FIRST_LESSON = "FIRST_LESSON"
FIRST_SKILL = "FIRST_SKILL"
XP_100 = "XP_100"
STREAK_3 = "STREAK_3"
STREAK_7 = "STREAK_7"
PERFECT_LESSON = "PERFECT_LESSON"


@dataclass(frozen=True)
class LearnerSnapshot:
    """Everything the predicates need, gathered in one pass.

    Collected up front so evaluating six achievements is four queries rather
    than one per achievement — and so each predicate below is a pure comparison
    that reads like the sentence in its description.
    """

    completed_lessons: int
    crowned_skills: int
    total_xp: int
    current_streak: int
    has_perfect_lesson: bool


def snapshot(db: Session, user: User) -> LearnerSnapshot:
    """Read the learner's current standing."""
    completed_lessons = db.scalar(
        select(func.count())
        .select_from(LessonAttempt)
        .where(LessonAttempt.user_id == user.id, LessonAttempt.completed.is_(True))
    )
    crowned_skills = db.scalar(
        select(func.count())
        .select_from(UserSkillProgress)
        .where(UserSkillProgress.user_id == user.id, UserSkillProgress.crowns >= 1)
    )
    stats = db.get(UserStats, user.id)
    perfect = db.scalar(
        select(LessonAttempt.id)
        .where(
            LessonAttempt.user_id == user.id,
            LessonAttempt.completed.is_(True),
            LessonAttempt.incorrect_answers == 0,
            # A lesson with no answers is not a perfect lesson.
            LessonAttempt.correct_answers > 0,
        )
        .limit(1)
    )

    return LearnerSnapshot(
        completed_lessons=completed_lessons or 0,
        crowned_skills=crowned_skills or 0,
        total_xp=stats.total_xp if stats else 0,
        current_streak=stats.current_streak if stats else 0,
        has_perfect_lesson=perfect is not None,
    )


#: key -> predicate. Adding an achievement is one entry here plus one seed row.
PREDICATES = {
    FIRST_LESSON: lambda s: s.completed_lessons >= 1,
    FIRST_SKILL: lambda s: s.crowned_skills >= 1,
    XP_100: lambda s: s.total_xp >= 100,
    STREAK_3: lambda s: s.current_streak >= 3,
    STREAK_7: lambda s: s.current_streak >= 7,
    PERFECT_LESSON: lambda s: s.has_perfect_lesson,
}


def evaluate(db: Session, user: User) -> list[Achievement]:
    """Award any achievement the learner now qualifies for.

    **Idempotent by construction.** Already-unlocked achievements are excluded
    before anything is evaluated, so a second call awards nothing — and
    `UNIQUE(user_id, achievement_id)` is the backstop if two calls ever race.

    Does **not** commit: the caller owns the transaction, so achievements are
    written in the same unit of work as the lesson completion that earned them
    (ADR-31 applies here too).

    @returns the achievements newly unlocked by this call, so the caller can
        report them to the client.
    """
    already = set(
        db.scalars(
            select(UserAchievement.achievement_id).where(
                UserAchievement.user_id == user.id
            )
        ).all()
    )

    candidates = db.scalars(
        select(Achievement).where(Achievement.id.notin_(already) if already else True)
    ).all()
    if not candidates:
        return []

    standing = snapshot(db, user)
    newly: list[Achievement] = []

    for achievement in candidates:
        predicate = PREDICATES.get(achievement.key)
        # An achievement in the database with no predicate is a seed/code
        # mismatch. Skipping is the safe response -- never award blindly.
        if predicate is None or not predicate(standing):
            continue
        db.add(
            UserAchievement(user_id=user.id, achievement_id=achievement.id)
        )
        newly.append(achievement)

    if newly:
        db.flush()
    return newly


def list_for_user(db: Session, user: User) -> list[tuple[Achievement, UserAchievement | None]]:
    """The whole catalogue, paired with this learner's unlock where it exists.

    Locked achievements have no row, so "locked" is the absence of one. Composing
    against the full catalogue here means the API can report locked achievements
    without the database storing a row per learner per unearned achievement.
    """
    unlocks = {
        row.achievement_id: row
        for row in db.scalars(
            select(UserAchievement).where(UserAchievement.user_id == user.id)
        ).all()
    }
    catalogue = db.scalars(
        select(Achievement).order_by(Achievement.order_index, Achievement.id)
    ).all()
    return [(item, unlocks.get(item.id)) for item in catalogue]
