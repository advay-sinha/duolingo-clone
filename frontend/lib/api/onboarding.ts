/**
 * Onboarding endpoints.
 *
 * Every one of these returns the **whole** onboarding status, not just the field
 * it changed. That is why nothing here merges a response into remembered state:
 * the client asks, is told where it is, and navigates. The sequence lives on the
 * server, which is what makes it survive a refresh or a login on another device.
 *
 * None of these functions takes a user id, and none of the request bodies has a
 * field for one. Who is asking comes from the session cookie.
 */

import { request } from "./client.ts";
import type {
  OnboardingStatus,
  ProficiencyLevel,
  StartingMode,
} from "./types";

/** Where the learner is in onboarding. */
export function getOnboardingStatus(
  init?: RequestInit,
): Promise<OnboardingStatus> {
  return request<OnboardingStatus>("/onboarding", init);
}

/**
 * Enrol in a course.
 *
 * The id is validated against the courses table, which is what makes the
 * picker's "coming soon" tiles unselectable in fact rather than only in CSS —
 * they have no row, so there is no id to send.
 */
export function selectCourse(courseId: number): Promise<OnboardingStatus> {
  return request<OnboardingStatus>("/onboarding/course", {
    method: "POST",
    body: JSON.stringify({ course_id: courseId }),
  });
}

/** Record the learner's self-reported proficiency. */
export function selectProficiency(
  proficiency: ProficiencyLevel,
): Promise<OnboardingStatus> {
  return request<OnboardingStatus>("/onboarding/proficiency", {
    method: "POST",
    body: JSON.stringify({ proficiency }),
  });
}

/**
 * Record the starting point.
 *
 * `SCRATCH` finishes onboarding; `PLACEMENT` leaves it open until the test is
 * done, which is what lets a learner close the tab mid-test and be returned to
 * it.
 */
export function selectStartingMode(
  mode: StartingMode,
): Promise<OnboardingStatus> {
  return request<OnboardingStatus>("/onboarding/start", {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
}
