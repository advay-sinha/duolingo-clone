"""ORM models.

Importing this package imports every model, which is what registers them on
``Base.metadata``. Anything that calls ``create_all`` must import this first, or
SQLAlchemy will create only the tables it happens to have seen.
"""

from app.models.content import (
    Course,
    Exercise,
    ExerciseType,
    Lesson,
    Skill,
    Unit,
)
from app.models.progress import LessonAttempt, UserSkillProgress
from app.models.user import User, UserStats

__all__ = [
    "Course",
    "Exercise",
    "ExerciseType",
    "Lesson",
    "LessonAttempt",
    "Skill",
    "Unit",
    "User",
    "UserSkillProgress",
    "UserStats",
]
