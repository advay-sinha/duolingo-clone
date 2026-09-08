/**
 * Placement test endpoints.
 *
 * Three calls, and none of them can ask for a level. The client sends which
 * test and what the learner typed or tapped; the difficulty of the next
 * question, the verdict on this one, and the final placement are all decided by
 * the server from rows it wrote itself.
 *
 * There is no `getPlacement` — `startPlacement` is idempotent and returns the
 * open test with its current question, so resuming and starting are the same
 * call. One endpoint fewer, and no way for the two to disagree.
 */

import { request } from "./client.ts";
import type {
  AnswerPayload,
  PlacementAnswerResult,
  PlacementResult,
  PlacementState,
} from "./types";

/** Open the placement test, or resume the one already in progress. */
export function startPlacement(init?: RequestInit): Promise<PlacementState> {
  return request<PlacementState>("/placement/start", {
    method: "POST",
    ...init,
  });
}

/** Answer the current question and receive the next one. */
export function answerPlacement(body: {
  test_id: number;
  exercise_id: number;
  answer: AnswerPayload;
}): Promise<PlacementAnswerResult> {
  return request<PlacementAnswerResult>("/placement/answer", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Score the test, place the learner, and finish onboarding. Idempotent. */
export function completePlacement(testId: number): Promise<PlacementResult> {
  return request<PlacementResult>("/placement/complete", {
    method: "POST",
    body: JSON.stringify({ test_id: testId }),
  });
}
