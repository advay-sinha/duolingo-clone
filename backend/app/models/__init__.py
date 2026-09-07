"""ORM models.

Importing this package imports every model, which is what registers them on
``Base.metadata``. Anything that calls ``create_all`` must import this first, or
SQLAlchemy will create only the tables it happens to have seen.
"""

from app.models.achievement import Achievement, UserAchievement
from app.models.content import (
    Course,
    Exercise,
    ExerciseType,
    Lesson,
    Skill,
    Unit,
)
from app.models.progress import (
    LessonAttempt,
    LessonAttemptAnswer,
    LessonAttemptPair,
    UserSkillProgress,
)
from app.models.user import Session, User, UserStats

__all__ = [
    "Achievement",
    "Course",
    "Exercise",
    "ExerciseType",
    "Lesson",
    "LessonAttempt",
    "LessonAttemptAnswer",
    "LessonAttemptPair",
    "Session",
    "Skill",
    "Unit",
    "User",
    "UserAchievement",
    "UserSkillProgress",
    "UserStats",
]
