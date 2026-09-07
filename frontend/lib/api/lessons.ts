/**
 * Lesson engine endpoints.
 *
 * The whole lesson loop, in five calls. Note what these signatures do *not*
 * carry: no user id (the server knows who is calling) and no score on
 * completion (the server already knows what was answered). The client's job is
 * to render exercises and report what the learner did — never to decide whether
 * it was right.
 */

import { request } from "./client.ts";
import type {
  CompleteLessonRequest,
  CompleteLessonResponse,
  LessonResponse,
  StartLessonResponse,
  SubmitAnswerRequest,
  SubmitAnswerResponse,
  SubmitPairResponse,
} from "./types";

/**
 * Fetch a lesson and its exercises for rendering.
 *
 * The response contains no answers — see `ExercisePublic`.
 */
export function getLesson(lessonId: number): Promise<LessonResponse> {
  return request<LessonResponse>(`/lessons/${lessonId}`);
}

/**
 * Open a lesson session.
 *
 * Returns the `attempt_id` every subsequent answer must carry, plus the lesson
 * itself so the player can start with one request. Awards and deducts nothing.
 * Fails with 409 if the learner has no hearts left.
 */
export function startLesson(lessonId: number): Promise<StartLessonResponse> {
  return request<StartLessonResponse>(`/lessons/${lessonId}/start`, {
    method: "POST",
  });
}

/**
 * Submit one answer for grading.
 *
 * Safe to retry: resubmitting the same exercise replays the original verdict
 * with `already_answered: true` rather than deducting a second heart. That makes
 * it safe to call again after a dropped connection.
 */
export function submitAnswer(
  lessonId: number,
  body: SubmitAnswerRequest,
): Promise<SubmitAnswerResponse> {
  return request<SubmitAnswerResponse>(`/lessons/${lessonId}/answer`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/**
 * Grade one match-pairs selection, the moment it is made.
 *
 * A separate endpoint from `submitAnswer` because it carries a different thing:
 * one move inside an exercise that is still in progress, rather than a finished
 * answer to it. The server decides whether the pair matches — the client sends
 * two ids and is told.
 *
 * Safe to retry: the same pair sent twice replays the first verdict with
 * `already_answered: true` and costs no second heart.
 */
export function submitPair(
  lessonId: number,
  body: {
    attempt_id: number;
    exercise_id: number;
    left_id: string;
    right_id: string;
  },
): Promise<SubmitPairResponse> {
  return request<SubmitPairResponse>(`/lessons/${lessonId}/pair`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/**
 * Finish the lesson and settle XP, streak, skill progress and crowns.
 *
 * The request carries only the attempt id — the server derives everything else
 * from the answers it recorded. Fails with 409 if the attempt is already
 * complete or if some exercises are unanswered.
 */
export function completeLesson(
  lessonId: number,
  body: CompleteLessonRequest,
): Promise<CompleteLessonResponse> {
  return request<CompleteLessonResponse>(`/lessons/${lessonId}/complete`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
