"""The learning path service — the first real business logic in the application.

Its job is to turn *content* (a course tree) plus *progress* (what one learner
has done) into the *path* the UI renders — including the skill states that exist
in no database column.

**What it must not do,** and why the boundaries are worth defending:

* No HTTP. It raises ``NotFoundError``, not ``HTTPException``, so it stays
  callable from a test or a future CLI command without importing FastAPI.
* No SQL. Every query comes from a repository, so this file reads as rules.
* No rendering. It returns schema objects, not markup or colours.

The unlock rule lives here rather than in a route because it is a domain rule.
If it lived in the route, the second consumer of the path — a mobile client, a
test, an admin preview — would either duplicate it or get it wrong, and the two
copies would drift.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import Skill, User, UserSkillProgress
from app.repositories import course_repo, progress_repo
from app.schemas.path import (
    CoursePathResponse,
    LessonNode,
    SkillNode,
    SkillState,
    UnitNode,
)


def _skill_state(
    progress: UserSkillProgress | None,
    previous_progress: UserSkillProgress | None,
    is_first: bool,
) -> SkillState:
    """Decide one skill's state for one learner.

    The rule, in full:

    * ``COMPLETED`` — this skill has at least one crown.
    * ``AVAILABLE`` — it is the very first skill of the course, **or** the skill
      immediately before it has at least one crown.
    * ``LOCKED`` — otherwise.

    A crown means "every lesson in this skill has been completed", so
    "``crowns >= 1``" is the same statement as "the learner finished it". Using
    crowns rather than ``lessons_completed >= total_lessons`` keeps the unlock
    condition a single integer comparison and avoids needing the *previous*
    skill's lesson count here.

    ``None`` progress is treated as zero rather than as an error: a learner who
    has never touched a skill legitimately has no row, and the seed happening to
    create zeroed rows should not be something this rule depends on.
    """
    crowns = progress.crowns if progress else 0
    if crowns >= 1:
        return SkillState.COMPLETED

    if is_first:
        return SkillState.AVAILABLE

    previous_crowns = previous_progress.crowns if previous_progress else 0
    return SkillState.AVAILABLE if previous_crowns >= 1 else SkillState.LOCKED


def build_path(db: Session, course_id: int, user: User) -> CoursePathResponse:
    """Assemble the full learning path for one course and one learner.

    Raises:
        NotFoundError: if no course has that id. The route turns this into a
            404. Returning an empty path with 200 would leave a client unable to
            tell "this course has no content" from "this course does not exist" —
            a typo'd URL would render as "you have finished everything".
    """
    course = course_repo.get_course_tree(db, course_id)
    if course is None:
        raise NotFoundError(f"Course {course_id} does not exist.")

    # Two queries for the learner's entire progress, regardless of course size.
    progress_by_skill = progress_repo.skill_progress_map(db, user.id)
    completed_lessons = progress_repo.completed_lesson_ids(db, user.id)

    # The unlock rule is about the skill *immediately before* this one, and that
    # predecessor may live in the previous unit -- so the ordering is global
    # across the course, not per unit. Flattening once here means the walk below
    # never has to look backwards across a unit boundary.
    ordered_skills: list[Skill] = [
        skill for unit in course.units for skill in unit.skills
    ]
    position_of = {skill.id: index for index, skill in enumerate(ordered_skills)}

    units: list[UnitNode] = []
    for unit in course.units:
        skill_nodes: list[SkillNode] = []

        for skill in unit.skills:
            index = position_of[skill.id]
            progress = progress_by_skill.get(skill.id)
            previous_progress = (
                progress_by_skill.get(ordered_skills[index - 1].id)
                if index > 0
                else None
            )

            lesson_nodes = [
                LessonNode(
                    id=lesson.id,
                    title=lesson.title,
                    order_index=lesson.order_index,
                    xp_reward=lesson.xp_reward,
                    completed=lesson.id in completed_lessons,
                )
                for lesson in skill.lessons
            ]

            skill_nodes.append(
                SkillNode(
                    id=skill.id,
                    title=skill.title,
                    description=skill.description,
                    order_index=skill.order_index,
                    icon=skill.icon,
                    state=_skill_state(
                        progress, previous_progress, is_first=index == 0
                    ),
                    crowns=progress.crowns if progress else 0,
                    # Counted from the completed-lesson set rather than read from
                    # progress.lessons_completed, so the two representations can
                    # never disagree in the response. The stored counter stays
                    # the fast path for aggregate reads; this endpoint already
                    # holds the precise data.
                    lessons_completed=sum(1 for node in lesson_nodes if node.completed),
                    total_lessons=len(lesson_nodes),
                    xp_earned=progress.xp_earned if progress else 0,
                    lessons=lesson_nodes,
                )
            )

        units.append(
            UnitNode(
                id=unit.id,
                title=unit.title,
                description=unit.description,
                order_index=unit.order_index,
                color_key=unit.color_key,
                skills=skill_nodes,
            )
        )

    return CoursePathResponse(
        course_id=course.id,
        course_title=course.title,
        source_language=course.source_language,
        target_language=course.target_language,
        units=units,
    )
