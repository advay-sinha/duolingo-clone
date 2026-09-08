/**
 * The onboarding option lists.
 *
 * These look like tests of constants, and two of them genuinely are — but they
 * pin things the UI's correctness rests on: that the five stored values match the
 * backend's enum exactly, and that the strength meter is monotonic, which is the
 * only reason the ladder reads at a glance.
 */

import assert from "node:assert/strict";
import test from "node:test";

import type { ProficiencyLevel } from "@/lib/api/types";

import {
  COMING_SOON_COURSES,
  courseFlag,
  PROFICIENCY_BARS,
  PROFICIENCY_OPTIONS,
  STARTING_POINT_OPTIONS,
} from "./options.ts";

test("there are exactly five proficiency options", () => {
  assert.equal(PROFICIENCY_OPTIONS.length, 5);
});

test("the proficiency values match the backend enum", () => {
  const expected: ProficiencyLevel[] = [
    "BEGINNER",
    "COMMON_WORDS",
    "BASIC_CONVERSATION",
    "VARIOUS_TOPICS",
    "ADVANCED",
  ];
  assert.deepEqual(
    PROFICIENCY_OPTIONS.map((option) => option.value),
    expected,
  );
});

test("proficiency strength increases down the list and fits the meter", () => {
  const strengths = PROFICIENCY_OPTIONS.map((option) => option.strength);

  for (let i = 1; i < strengths.length; i += 1) {
    assert.ok(
      strengths[i] > strengths[i - 1],
      `option ${i} is not stronger than the one above it`,
    );
  }
  assert.ok(Math.max(...strengths) <= PROFICIENCY_BARS);
  assert.ok(Math.min(...strengths) >= 0);
});

test("every proficiency option has a label a learner can read", () => {
  for (const option of PROFICIENCY_OPTIONS) {
    assert.ok(option.label.length > 0);
    assert.notEqual(option.label, option.value);
  }
});

test("the two starting points are scratch and placement", () => {
  assert.deepEqual(
    STARTING_POINT_OPTIONS.map((option) => option.value),
    ["SCRATCH", "PLACEMENT"],
  );
});

test("the starting points carry the copy from the design", () => {
  const [scratch, placement] = STARTING_POINT_OPTIONS;
  assert.equal(scratch.title, "Start from scratch");
  assert.equal(
    scratch.description,
    "Take the easiest lesson of the Spanish course",
  );
  assert.equal(placement.title, "Find my level");
  assert.equal(
    placement.description,
    "Let Duo recommend where you should start learning",
  );
});

test("no coming-soon course carries an id that could be submitted", () => {
  // The point of the list: these are presentation. If one of them ever grew a
  // numeric course id, it would become selectable and this test would say so.
  for (const course of COMING_SOON_COURSES) {
    assert.equal(typeof course.key, "string");
    assert.ok(!("id" in course));
  }
});

test("coming-soon keys are unique", () => {
  const keys = COMING_SOON_COURSES.map((course) => course.key);
  assert.equal(new Set(keys).size, keys.length);
});

test("a course with no flag emoji still gets one", () => {
  assert.equal(courseFlag("🇪🇸"), "🇪🇸");
  assert.equal(courseFlag(""), "🌍");
  assert.equal(courseFlag("   "), "🌍");
});
