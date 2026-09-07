/**
 * Course endpoints.
 *
 * One module per backend resource, each exporting typed functions. Components
 * call these; they never see a URL and never call `fetch`.
 */

import { request } from "./client.ts";
import type { CourseListResponse, CoursePathResponse } from "./types";

/** List the available courses. */
export function getCourses(init?: RequestInit): Promise<CourseListResponse> {
  return request<CourseListResponse>("/courses", init);
}

/**
 * Fetch the full learning path for a course, with the current learner's
 * progress and each skill's derived state.
 *
 * One request populates the entire learn screen — units, skills, lessons and
 * lock state together — so the screen cannot render half-populated.
 */
export function getCoursePath(
  courseId: number,
  init?: RequestInit,
): Promise<CoursePathResponse> {
  return request<CoursePathResponse>(`/courses/${courseId}/path`, init);
}
