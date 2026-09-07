/**
 * Tests for the lesson session state machine.
 *
 * The reducer is pure, so the whole lesson flow — start, draft, submit, verdict,
 * continue, complete, fail — is testable with no DOM, no renderer and no mocks.
 * These are the tests that actually cover the behaviours the phase cares about:
 * duplicate-submission protection, hearts coming from the server, advancing to
 * the next exercise, and completion being server-driven.
 */

import assert from "node:assert/strict";
import test from "node:test";

import type {
  CompleteLessonResponse,
  ExercisePublic,
  LessonResponse,
  SubmitAnswerResponse,
} from "@/lib/api/types";
import {
  canSubmit,
  currentExercise,
  initialState,
  isLastExercise,
  reduce,
  type SessionState,
} from "./session.ts";

// --------------------------------------------------------------------------
// Fixtures
// --------------------------------------------------------------------------

function exercise(id: number, type: ExercisePublic["type"]): ExercisePublic {
  return {
    id,
    type,
    order_index: id - 1,
    instruction: "",
    prompt: `Prompt ${id}`,
    data: {},
  };
}

const LESSON: LessonResponse = {
  id: 1,
  title: "Hello and goodbye",
  order_index: 0,
  xp_reward: 10,
  skill: { id: 1, title: "Greetings" },
  exercises: [
    exercise(1, "MULTIPLE_CHOICE"),
    exercise(2, "TRANSLATE"),
    exercise(3, "TYPE_ANSWER"),
  ],
};

function verdict(over: Partial<SubmitAnswerResponse> = {}): SubmitAnswerResponse {
  return {
    correct: true,
    correct_answer: null,
    xp_earned: 10,
    hearts_remaining: 5,
    already_answered: false,
    answered_count: 1,
    total_exercises: 3,
    ...over,
  };
}

const COMPLETION: CompleteLessonResponse = {
  attempt_id: 7,
  lesson_id: 1,
  correct_answers: 3,
  incorrect_answers: 0,
  total_exercises: 3,
  accuracy: 1,
  xp_earned: 40,
  first_completion: true,
  total_xp: 40,
  daily_xp: 40,
  daily_goal: 30,
  hearts_remaining: 5,
  current_streak: 1,
  longest_streak: 1,
  streak_extended: true,
  skill_id: 1,
  lessons_completed: 1,
  total_lessons: 2,
  crowns: 0,
  crown_earned: false,
  achievements_unlocked: [],
};

/** A session that has started and is showing the first exercise. */
function started(): SessionState {
  return reduce(initialState, {
    type: "STARTED",
    lesson: LESSON,
    attemptId: 7,
    hearts: 5,
    maxHearts: 5,
  });
}

// --------------------------------------------------------------------------
// Starting
// --------------------------------------------------------------------------

test("starting a lesson stores the attempt and shows the first exercise", () => {
  const state = started();

  assert.equal(state.status, "active");
  assert.equal(state.attemptId, 7);
  assert.equal(state.index, 0);
  assert.equal(state.hearts, 5);
  assert.equal(currentExercise(state)?.id, 1);
});

// --------------------------------------------------------------------------
// Draft and submit gating
// --------------------------------------------------------------------------

test("submit is blocked until an answer has been drafted", () => {
  const state = started();
  assert.equal(canSubmit(state), false);

  const withDraft = reduce(state, {
    type: "DRAFT_CHANGED",
    draft: { option_id: "o1" },
  });
  assert.equal(canSubmit(withDraft), true);
});

test("clearing the draft disables submit again", () => {
  let state = started();
  state = reduce(state, { type: "DRAFT_CHANGED", draft: { text: "hola" } });
  state = reduce(state, { type: "DRAFT_CHANGED", draft: null });

  assert.equal(canSubmit(state), false);
});

test("submit is blocked while a request is in flight", () => {
  let state = started();
  state = reduce(state, { type: "DRAFT_CHANGED", draft: { option_id: "o1" } });
  state = reduce(state, { type: "SUBMIT_STARTED" });

  assert.equal(state.submission, "submitting");
  assert.equal(canSubmit(state), false);
});

test("a second SUBMIT_STARTED is ignored", () => {
  let state = started();
  state = reduce(state, { type: "DRAFT_CHANGED", draft: { option_id: "o1" } });
  const first = reduce(state, { type: "SUBMIT_STARTED" });
  const second = reduce(first, { type: "SUBMIT_STARTED" });

  // Same object back: the duplicate is a no-op, so no second request fires.
  assert.equal(second, first);
});

test("the draft cannot be changed after the answer is graded", () => {
  let state = started();
  state = reduce(state, { type: "DRAFT_CHANGED", draft: { option_id: "o1" } });
  state = reduce(state, { type: "SUBMIT_STARTED" });
  state = reduce(state, { type: "ANSWER_RECEIVED", verdict: verdict() });

  const tampered = reduce(state, {
    type: "DRAFT_CHANGED",
    draft: { option_id: "o2" },
  });

  assert.deepEqual(tampered.draft, { option_id: "o1" });
});

test("submit is blocked with no hearts left", () => {
  let state = started();
  state = reduce(state, { type: "DRAFT_CHANGED", draft: { option_id: "o1" } });
  state = { ...state, hearts: 0 };

  assert.equal(canSubmit(state), false);
});

// --------------------------------------------------------------------------
// Verdicts — the server is the source of truth
// --------------------------------------------------------------------------

test("hearts come from the server response, not from local arithmetic", () => {
  let state = started();
  state = reduce(state, { type: "DRAFT_CHANGED", draft: { option_id: "o1" } });
  state = reduce(state, { type: "SUBMIT_STARTED" });
  state = reduce(state, {
    type: "ANSWER_RECEIVED",
    verdict: verdict({ correct: false, hearts_remaining: 3, xp_earned: 0 }),
  });

  // 5 -> 3 in one step: only the server could have decided that.
  assert.equal(state.hearts, 3);
  assert.equal(state.verdict?.correct, false);
  assert.equal(state.submission, "answered");
});

test("an incorrect verdict carries the expected answer for feedback", () => {
  let state = started();
  state = reduce(state, { type: "DRAFT_CHANGED", draft: { text: "wrong" } });
  state = reduce(state, { type: "SUBMIT_STARTED" });
  state = reduce(state, {
    type: "ANSWER_RECEIVED",
    verdict: verdict({
      correct: false,
      correct_answer: "buenos días",
      hearts_remaining: 4,
    }),
  });

  assert.equal(state.verdict?.correct_answer, "buenos días");
});

// --------------------------------------------------------------------------
// Advancing
// --------------------------------------------------------------------------

test("continue advances to the next exercise and clears the previous answer", () => {
  let state = started();
  state = reduce(state, { type: "DRAFT_CHANGED", draft: { option_id: "o1" } });
  state = reduce(state, { type: "SUBMIT_STARTED" });
  state = reduce(state, { type: "ANSWER_RECEIVED", verdict: verdict() });
  state = reduce(state, { type: "CONTINUE" });

  assert.equal(state.index, 1);
  assert.equal(currentExercise(state)?.id, 2);
  assert.equal(state.draft, null);
  assert.equal(state.verdict, null);
  assert.equal(state.submission, "ready");
});

test("isLastExercise is only true on the final exercise", () => {
  let state = started();
  assert.equal(isLastExercise(state), false);

  state = reduce(state, { type: "CONTINUE" });
  assert.equal(isLastExercise(state), false);

  state = reduce(state, { type: "CONTINUE" });
  assert.equal(isLastExercise(state), true);
});

// --------------------------------------------------------------------------
// Completion
// --------------------------------------------------------------------------

test("completion stores the server's summary verbatim", () => {
  let state = started();
  state = reduce(state, { type: "COMPLETE_STARTED" });
  assert.equal(state.status, "completing");

  state = reduce(state, { type: "COMPLETED", completion: COMPLETION });

  assert.equal(state.status, "completed");
  assert.equal(state.completion?.xp_earned, 40);
  assert.equal(state.completion?.current_streak, 1);
  assert.equal(state.hearts, 5);
});

test("a practice completion reporting zero XP is stored as-is", () => {
  let state = started();
  state = reduce(state, {
    type: "COMPLETED",
    completion: { ...COMPLETION, first_completion: false, xp_earned: 0 },
  });

  // The UI must show what the server said, not a number it invented.
  assert.equal(state.completion?.xp_earned, 0);
  assert.equal(state.completion?.first_completion, false);
});

// --------------------------------------------------------------------------
// Errors
// --------------------------------------------------------------------------

test("a load failure replaces the screen", () => {
  const state = reduce(initialState, {
    type: "FAILED",
    error: { stage: "load", outOfHearts: false, message: "boom" },
  });

  assert.equal(state.status, "failed");
  assert.equal(state.error?.message, "boom");
});

test("an answer failure keeps the lesson on screen and allows a retry", () => {
  let state = started();
  state = reduce(state, { type: "DRAFT_CHANGED", draft: { option_id: "o1" } });
  state = reduce(state, { type: "SUBMIT_STARTED" });
  state = reduce(state, {
    type: "FAILED",
    error: { stage: "answer", outOfHearts: false, message: "network" },
  });

  assert.equal(state.status, "active");
  // Back to ready, so the learner can try again rather than being stuck.
  assert.equal(state.submission, "ready");
  assert.equal(canSubmit(state), true);
});

test("an out-of-hearts failure is flagged for a blocking state", () => {
  const state = reduce(initialState, {
    type: "FAILED",
    error: { stage: "load", outOfHearts: true, message: "no hearts" },
  });

  assert.equal(state.error?.outOfHearts, true);
});

test("a dismissed error clears without touching the session", () => {
  let state = started();
  state = reduce(state, {
    type: "FAILED",
    error: { stage: "answer", outOfHearts: false, message: "network" },
  });
  state = reduce(state, { type: "ERROR_DISMISSED" });

  assert.equal(state.error, null);
  assert.equal(state.status, "active");
});
