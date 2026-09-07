/**
 * The lesson session state machine.
 *
 * Kept as a **pure reducer in its own module**, separate from the React hook
 * that drives it, for one reason: every rule about how a lesson session
 * progresses can then be tested with no DOM, no renderer and no mocking — just
 * `reduce(state, action)`. The component becomes a thin shell over logic that is
 * already proven.
 *
 * The per-exercise state machine the reducer enforces:
 *
 *     READY ──submit──> SUBMITTING ──verdict──> ANSWERED ──continue──> READY
 *                            │                                          (next)
 *                            └──error──> READY (retryable)
 *
 * `SUBMITTING` exists specifically so the Check button can be disabled while a
 * request is in flight. The backend is idempotent (a resubmission replays the
 * original verdict), but the UI should still not fire the request twice — a
 * double-click should feel like nothing happened, not like a race.
 *
 * **No business rules live here.** Correctness, XP, hearts, streaks, crowns and
 * completion eligibility all arrive from the server; this reducer only records
 * them and decides what to show next.
 */

import type {
  CompleteLessonResponse,
  LessonResponse,
  SubmitAnswerResponse,
} from "@/lib/api/types";
import { assertNever } from "./exercise.ts";
import type { DraftAnswer } from "./exercise";

/** What the page as a whole is doing. */
export type SessionStatus =
  | "loading"
  | "active"
  | "completing"
  | "completed"
  | "failed";

/** What the current exercise is doing. */
export type SubmissionStatus = "ready" | "submitting" | "answered";

export interface SessionError {
  message: string;
  /** Which step failed, so the UI can offer the right recovery. */
  stage: "load" | "answer" | "complete";
  /** True when the learner has no hearts left — a blocking state, not a retry. */
  outOfHearts: boolean;
}

export interface SessionState {
  status: SessionStatus;
  lesson: LessonResponse | null;
  attemptId: number | null;

  /** Index of the exercise being shown. Drives the progress bar. */
  index: number;

  /** Hearts, as last reported by the server. Never decremented locally. */
  hearts: number;
  maxHearts: number;

  /** The current exercise's draft answer, or null when not ready to submit. */
  draft: DraftAnswer;
  submission: SubmissionStatus;

  /** The server's verdict for the current exercise, once answered. */
  verdict: SubmitAnswerResponse | null;

  /** The server's completion summary, once the lesson is finished. */
  completion: CompleteLessonResponse | null;

  error: SessionError | null;
}

export const initialState: SessionState = {
  status: "loading",
  lesson: null,
  attemptId: null,
  index: 0,
  hearts: 0,
  maxHearts: 5,
  draft: null,
  submission: "ready",
  verdict: null,
  completion: null,
  error: null,
};

export type SessionAction =
  | {
      type: "STARTED";
      lesson: LessonResponse;
      attemptId: number;
      hearts: number;
      maxHearts: number;
    }
  | { type: "DRAFT_CHANGED"; draft: DraftAnswer }
  | { type: "SUBMIT_STARTED" }
  | { type: "ANSWER_RECEIVED"; verdict: SubmitAnswerResponse }
  // Phase 9: match pairs is graded a pair at a time, so hearts can change
  // several times inside one exercise without the exercise being answered yet.
  // The value comes from the server's response, like every other heart update.
  | { type: "HEARTS_UPDATED"; hearts: number }
  | { type: "CONTINUE" }
  | { type: "COMPLETE_STARTED" }
  | { type: "COMPLETED"; completion: CompleteLessonResponse }
  | { type: "FAILED"; error: SessionError }
  | { type: "ERROR_DISMISSED" };

/** True when the exercise on screen is the last one in the lesson. */
export function isLastExercise(state: SessionState): boolean {
  if (!state.lesson) return false;
  return state.index >= state.lesson.exercises.length - 1;
}

/** The exercise currently being shown, if any. */
export function currentExercise(state: SessionState) {
  return state.lesson?.exercises[state.index] ?? null;
}

/**
 * Whether the Check button should be enabled.
 *
 * The only client-side judgement about an answer: *is there one yet*. Never
 * whether it is right.
 */
export function canSubmit(state: SessionState): boolean {
  return (
    state.status === "active" &&
    state.submission === "ready" &&
    state.draft !== null &&
    state.hearts > 0
  );
}

export function reduce(
  state: SessionState,
  action: SessionAction,
): SessionState {
  switch (action.type) {
    case "STARTED":
      return {
        ...state,
        status: "active",
        lesson: action.lesson,
        attemptId: action.attemptId,
        hearts: action.hearts,
        maxHearts: action.maxHearts,
        index: 0,
        draft: null,
        submission: "ready",
        verdict: null,
        error: null,
      };

    case "DRAFT_CHANGED":
      // Ignored once answered: the verdict is in, and letting the learner keep
      // fiddling with a graded exercise would imply they could change it.
      if (state.submission !== "ready") return state;
      return { ...state, draft: action.draft };

    case "SUBMIT_STARTED":
      // The guard that makes double-submission impossible from the UI side.
      if (state.submission !== "ready") return state;
      return { ...state, submission: "submitting", error: null };

    case "HEARTS_UPDATED":
      // Deliberately touches nothing else. A wrong pair costs a heart but is not
      // an answer: the exercise stays in progress and the learner keeps going.
      return { ...state, hearts: action.hearts };

    case "ANSWER_RECEIVED":
      return {
        ...state,
        submission: "answered",
        verdict: action.verdict,
        // Hearts come from the server, never computed here.
        hearts: action.verdict.hearts_remaining,
      };

    case "CONTINUE":
      return {
        ...state,
        index: state.index + 1,
        draft: null,
        submission: "ready",
        verdict: null,
      };

    case "COMPLETE_STARTED":
      return { ...state, status: "completing", error: null };

    case "COMPLETED":
      return {
        ...state,
        status: "completed",
        completion: action.completion,
        hearts: action.completion.hearts_remaining,
      };

    case "FAILED":
      return {
        ...state,
        // A failure to load leaves nothing to show; a failure mid-lesson leaves
        // the lesson on screen so the learner can retry or leave.
        status: action.error.stage === "load" ? "failed" : state.status,
        submission: state.submission === "submitting" ? "ready" : state.submission,
        error: action.error,
      };

    case "ERROR_DISMISSED":
      return { ...state, error: null };

    default:
      // Exhaustiveness: an unhandled action type is a compile error.
      return assertNever(action, state);
  }
}
