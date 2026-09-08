/**
 * Tests for learning-path presentation logic.
 *
 * The theme running through these: **the client renders server state, it never
 * decides it.** Several tests deliberately construct data the real backend would
 * never send — a LOCKED skill with crowns, a COMPLETED skill with no lessons
 * done — to prove the UI follows `state` rather than second-guessing it from
 * progress numbers.
 */

import assert from "node:assert/strict";
import test from "node:test";

import type { LessonNode, SkillNode } from "@/lib/api/types";
import {
  isSkillPlayable,
  nodeOffset,
  ringFraction,
  selectNextLesson,
  skillStateLabel,
  skillVisual,
} from "./path.ts";

function lesson(id: number, completed: boolean): LessonNode {
  return {
    id,
    title: `Lesson ${id}`,
    order_index: id - 1,
    xp_reward: 10,
    completed,
  };
}

function skill(over: Partial<SkillNode> = {}): SkillNode {
  return {
    id: 1,
    title: "Greetings",
    description: "",
    order_index: 0,
    icon: "waving_hand",
    state: "AVAILABLE",
    crowns: 0,
    placed_out: false,
    lessons_completed: 0,
    total_lessons: 2,
    xp_earned: 0,
    lessons: [lesson(1, false), lesson(2, false)],
    ...over,
  };
}

// --------------------------------------------------------------------------
// Visual state — derived from the server's state, never recomputed
// --------------------------------------------------------------------------

test("a LOCKED skill renders locked", () => {
  assert.equal(skillVisual(skill({ state: "LOCKED" })), "locked");
});

test("an AVAILABLE skill with no progress renders available", () => {
  assert.equal(skillVisual(skill({ lessons_completed: 0 })), "available");
});

test("an AVAILABLE skill with progress renders in-progress", () => {
  assert.equal(skillVisual(skill({ lessons_completed: 1 })), "in-progress");
});

test("a COMPLETED skill renders completed", () => {
  assert.equal(
    skillVisual(skill({ state: "COMPLETED", crowns: 1, lessons_completed: 2 })),
    "completed",
  );
});

test("in-progress is a presentation variant, not a backend state", () => {
  // Both are AVAILABLE to the server; only the counts differ.
  const fresh = skill({ state: "AVAILABLE", lessons_completed: 0 });
  const started = skill({ state: "AVAILABLE", lessons_completed: 1 });

  assert.equal(fresh.state, started.state);
  assert.notEqual(skillVisual(fresh), skillVisual(started));
});

test("the server's state wins over local progress numbers", () => {
  // A LOCKED skill that somehow reports progress is still drawn locked: the
  // client does not infer state from counts.
  const contradictory = skill({ state: "LOCKED", lessons_completed: 2, crowns: 1 });
  assert.equal(skillVisual(contradictory), "locked");
});

// --------------------------------------------------------------------------
// Progress ring
// --------------------------------------------------------------------------

test("the ring uses lessons_completed over total_lessons", () => {
  assert.equal(ringFraction(skill({ lessons_completed: 0, total_lessons: 2 })), 0);
  assert.equal(ringFraction(skill({ lessons_completed: 1, total_lessons: 2 })), 0.5);
  assert.equal(ringFraction(skill({ lessons_completed: 2, total_lessons: 2 })), 1);
});

test("the ring handles a skill with no lessons without dividing by zero", () => {
  assert.equal(ringFraction(skill({ total_lessons: 0, lessons_completed: 0 })), 0);
});

test("the ring never exceeds full", () => {
  assert.equal(ringFraction(skill({ lessons_completed: 5, total_lessons: 2 })), 1);
});

// --------------------------------------------------------------------------
// Lesson selection
// --------------------------------------------------------------------------

test("a fresh skill opens its first lesson", () => {
  assert.equal(selectNextLesson(skill())?.id, 1);
});

test("a partly finished skill resumes at the first incomplete lesson", () => {
  const partial = skill({
    lessons_completed: 1,
    lessons: [lesson(1, true), lesson(2, false)],
  });
  assert.equal(selectNextLesson(partial)?.id, 2);
});

test("selection skips completed lessons even out of order", () => {
  const odd = skill({
    lessons: [lesson(1, true), lesson(2, true), lesson(3, false)],
    total_lessons: 3,
  });
  assert.equal(selectNextLesson(odd)?.id, 3);
});

test("a fully completed skill offers its last lesson for practice", () => {
  // Replay is a real backend capability: a repeat completion is accepted and
  // awards no XP. Nothing new was invented to support this.
  const done = skill({
    state: "COMPLETED",
    crowns: 1,
    lessons_completed: 2,
    lessons: [lesson(1, true), lesson(2, true)],
  });
  assert.equal(selectNextLesson(done)?.id, 2);
});

test("a skill with no lessons selects nothing", () => {
  assert.equal(selectNextLesson(skill({ lessons: [], total_lessons: 0 })), null);
});

// --------------------------------------------------------------------------
// Playability
// --------------------------------------------------------------------------

test("locked skills are not playable", () => {
  assert.equal(isSkillPlayable(skill({ state: "LOCKED" })), false);
});

test("available and completed skills are playable", () => {
  assert.equal(isSkillPlayable(skill({ state: "AVAILABLE" })), true);
  assert.equal(isSkillPlayable(skill({ state: "COMPLETED" })), true);
});

test("a skill with no lessons is not playable", () => {
  assert.equal(isSkillPlayable(skill({ lessons: [] })), false);
});

// --------------------------------------------------------------------------
// Layout and labels
// --------------------------------------------------------------------------

test("node offsets repeat in a fixed cycle so the path is stable", () => {
  const offsets = [0, 1, 2, 3, 4, 5].map((i) => nodeOffset(i, 50));
  assert.deepEqual(offsets, [0, 50, 0, -50, 0, 50]);
});

test("each state has a distinct screen-reader label", () => {
  const labels = [
    skillStateLabel(skill({ state: "LOCKED" })),
    skillStateLabel(skill({ lessons_completed: 0 })),
    skillStateLabel(skill({ lessons_completed: 1 })),
    skillStateLabel(skill({ state: "COMPLETED", crowns: 1 })),
  ];

  assert.equal(new Set(labels).size, 4);
  assert.match(labels[0], /Locked/);
  assert.match(labels[3], /1 crown\b/);
});

test("the label pluralises crowns correctly", () => {
  assert.match(skillStateLabel(skill({ state: "COMPLETED", crowns: 2 })), /2 crowns/);
});
