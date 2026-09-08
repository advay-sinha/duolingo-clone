/**
 * Presentation logic for the learning path — pure functions.
 *
 * **What is deliberately absent from this file: the unlock rule.** Whether a
 * skill is locked, available or completed is decided by the backend's
 * `PathService` and arrives in `skill.state`. Recreating
 * `if (previous.crowns >= 1)` here would be a second implementation of a domain
 * rule that could drift from the real one — the exact mistake the architecture
 * exists to prevent.
 *
 * What *is* here is presentation: turning server values into the things a
 * renderer needs (a fraction for a ring, a visual variant, which lesson a click
 * should open). All pure, so it is testable without a DOM — the same approach
 * as `lib/lesson/`.
 */

import type { LessonNode, SkillNode } from "@/lib/api/types";

/**
 * The visual variant of a skill node.
 *
 * Five variants over four domain states. `in-progress` is **not** a backend
 * state and must never become one: it is `AVAILABLE` with at least one lesson
 * done, which the response already tells us. The Stitch design draws that node
 * differently (a partial progress ring), so the distinction is real — but it is
 * a rendering concern, derived from data the server already sent.
 *
 * `placed-out` is the opposite case: a genuine backend state, because nothing
 * else in the response could tell the client that a placement test carried the
 * learner past this skill.
 */
export type SkillVisual =
  | "locked"
  | "available"
  | "in-progress"
  | "completed"
  | "placed-out";

export function skillVisual(skill: SkillNode): SkillVisual {
  if (skill.state === "COMPLETED") return "completed";
  // Phase 9.5. Unlike `in-progress`, this *is* a backend state: the server knows
  // the learner was placed beyond this skill and the client could not derive it
  // from anything else in the response. It is drawn differently from a crowned
  // skill on purpose — the learner never did these lessons, and a gold crown
  // would say they had.
  if (skill.state === "PLACED_OUT") return "placed-out";
  if (skill.state === "LOCKED") return "locked";
  return skill.lessons_completed > 0 ? "in-progress" : "available";
}

/**
 * Progress around the ring, 0–1.
 *
 * `lessons_completed / total_lessons`, exactly as the API reports them — the
 * server sends counts and the client renders the ratio (backend ADR-21). Guards
 * against a divide-by-zero for a skill with no lessons.
 */
export function ringFraction(skill: SkillNode): number {
  if (skill.total_lessons <= 0) return 0;
  return Math.min(1, skill.lessons_completed / skill.total_lessons);
}

/**
 * Choose which lesson a click on this skill should open.
 *
 * **The rule: the first lesson that is not yet completed.** That makes "Start"
 * and "Continue" the same action — a learner resumes where they left off without
 * the UI having to track anything.
 *
 * If every lesson is complete, the last one is returned so the skill can be
 * replayed. That is not an invented mode: Phase 4's `complete` endpoint already
 * accepts a repeat completion and deliberately awards 0 XP
 * (`first_completion: false`), so replay is a capability the backend genuinely
 * has. Nothing new was added to support it.
 *
 * @returns the lesson to open, or `null` for a skill with no lessons.
 */
export function selectNextLesson(skill: SkillNode): LessonNode | null {
  if (skill.lessons.length === 0) return null;
  const incomplete = skill.lessons.find((lesson) => !lesson.completed);
  return incomplete ?? skill.lessons[skill.lessons.length - 1];
}

/** True when a click on this skill should lead into a lesson. */
export function isSkillPlayable(skill: SkillNode): boolean {
  return skill.state !== "LOCKED" && skill.lessons.length > 0;
}

/**
 * Horizontal offset for a node, in pixels, to produce Stitch's winding path.
 *
 * A repeating 0, +1, 0, −1 cycle rather than random or computed geometry: it is
 * deterministic (the path looks the same on every render), it needs no SVG, and
 * it degrades to a straight column on narrow screens where the callers drop it.
 */
const WIND = [0, 1, 0, -1];

export function nodeOffset(index: number, amplitude = 56): number {
  return WIND[index % WIND.length] * amplitude;
}

/**
 * Accessible description of a skill's state, for screen readers.
 *
 * The visual states are conveyed with colour and iconography, neither of which
 * a screen reader can use, so each node carries this sentence instead.
 */
export function skillStateLabel(skill: SkillNode): string {
  switch (skillVisual(skill)) {
    case "locked":
      return "Locked. Complete the previous skill to unlock.";
    case "completed":
      return `Completed. ${skill.crowns} crown${skill.crowns === 1 ? "" : "s"} earned.`;
    case "placed-out":
      return `Placed out by your placement test. Not yet studied — ${skill.total_lessons} lesson${skill.total_lessons === 1 ? "" : "s"} available to practise.`;
    case "in-progress":
      return `In progress. ${skill.lessons_completed} of ${skill.total_lessons} lessons complete.`;
    default:
      return `Available. ${skill.total_lessons} lesson${skill.total_lessons === 1 ? "" : "s"}.`;
  }
}
