/**
 * Onboarding routing, tested as pure functions.
 *
 * `node --test`, no DOM and no React — the routing rules are decidable from a
 * status object, so they are testable in milliseconds. What is *not* tested here
 * is the order of the steps, because this module does not decide it: the server
 * does, and asserting it here would be asserting a duplicate.
 */

import assert from "node:assert/strict";
import test from "node:test";

import type { OnboardingStatus } from "@/lib/api/types";

import { redirectFor, routeForStatus, STEP_ROUTES, stepProgress } from "./steps.ts";

function status(over: Partial<OnboardingStatus> = {}): OnboardingStatus {
  return {
    completed: false,
    step: "COURSE",
    course_id: null,
    proficiency: null,
    starting_mode: null,
    placement: null,
    grandfathered: false,
    completed_at: null,
    ...over,
  };
}

test("every step has a route", () => {
  for (const step of [
    "COURSE",
    "PROFICIENCY",
    "START",
    "PLACEMENT",
    "DONE",
  ] as const) {
    assert.equal(typeof STEP_ROUTES[step], "string");
    assert.ok(STEP_ROUTES[step].startsWith("/"));
  }
});

test("a finished learner is routed to the learning path", () => {
  assert.equal(routeForStatus(status({ completed: true, step: "DONE" })), "/learn");
});

test("a learner who registered before onboarding existed goes straight to /learn", () => {
  const grandfathered = status({
    completed: true,
    step: "DONE",
    grandfathered: true,
  });
  assert.equal(routeForStatus(grandfathered), "/learn");
  assert.equal(redirectFor(grandfathered, "COURSE"), "/learn");
});

test("a learner on the page they belong on is not redirected", () => {
  assert.equal(redirectFor(status({ step: "PROFICIENCY" }), "PROFICIENCY"), null);
});

test("skipping ahead sends the learner back to the step they are on", () => {
  // Typing /onboarding/placement without having chosen a course.
  assert.equal(
    redirectFor(status({ step: "COURSE" }), "PLACEMENT"),
    "/onboarding/course",
  );
});

test("going back to a finished step sends the learner forward again", () => {
  assert.equal(
    redirectFor(status({ step: "START", course_id: 1 }), "COURSE"),
    "/onboarding/start",
  );
});

test("progress increases with each step and completes at DONE", () => {
  assert.equal(stepProgress("COURSE"), 0);
  assert.ok(stepProgress("PROFICIENCY") > stepProgress("COURSE"));
  assert.ok(stepProgress("START") > stepProgress("PROFICIENCY"));
  assert.ok(stepProgress("PLACEMENT") > stepProgress("START"));
  assert.equal(stepProgress("DONE"), 1);
});

test("progress stays within 0 and 1", () => {
  for (const step of [
    "COURSE",
    "PROFICIENCY",
    "START",
    "PLACEMENT",
    "DONE",
  ] as const) {
    const value = stepProgress(step);
    assert.ok(value >= 0 && value <= 1, `${step} produced ${value}`);
  }
});
