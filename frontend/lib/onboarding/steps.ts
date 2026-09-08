/**
 * Onboarding routing — pure functions over the server's answer.
 *
 * **What is deliberately absent from this file: the order of the steps.** The
 * server decides which step a learner is on, from which of its columns are still
 * null, and sends it as `status.step`. This module only maps that value to a
 * URL. Recreating `if (!course) return "course"` here would be a second
 * implementation of a domain rule that could drift from the real one — the same
 * mistake `lib/learn/path.ts` refuses to make with the unlock rule.
 *
 * The payoff is concrete: refresh, back-button, logout-and-login and a
 * bookmarked deep link all behave correctly without a single line of code that
 * remembers anything.
 */

import type { OnboardingStatus, OnboardingStep } from "@/lib/api/types";

/** Where each step lives. */
export const STEP_ROUTES: Record<OnboardingStep, string> = {
  COURSE: "/onboarding/course",
  PROFICIENCY: "/onboarding/proficiency",
  START: "/onboarding/start",
  PLACEMENT: "/onboarding/placement",
  DONE: "/learn",
};

/** The route this learner belongs on right now. */
export function routeForStatus(status: OnboardingStatus): string {
  return STEP_ROUTES[status.step];
}

/**
 * Whether a learner sitting on `page` should be sent somewhere else.
 *
 * Returns the destination, or `null` to render the page as asked. Every
 * onboarding page calls this on the server before rendering, which is what stops
 * someone skipping ahead by typing a URL: the answer comes from the database,
 * not from what the browser navigated to.
 */
export function redirectFor(
  status: OnboardingStatus,
  page: OnboardingStep,
): string | null {
  if (status.step === page) return null;
  return STEP_ROUTES[status.step];
}

/**
 * Progress through onboarding, 0–1, for the bar at the top of each screen.
 *
 * Four steps, so reaching the placement screen shows three quarters. `DONE` is
 * a full bar, which the learner sees for the moment between finishing and the
 * navigation landing.
 */
const ORDER: OnboardingStep[] = ["COURSE", "PROFICIENCY", "START", "PLACEMENT"];

export function stepProgress(step: OnboardingStep): number {
  if (step === "DONE") return 1;
  const index = ORDER.indexOf(step);
  return index < 0 ? 0 : index / ORDER.length;
}
