"use client";

/**
 * The lesson session controller.
 *
 * **The only component in the lesson that talks to the API.** Exercise
 * components render payloads and report drafts; this one owns the attempt, makes
 * every request, and feeds server responses into the reducer. That boundary is
 * what keeps five renderers free of HTTP concerns and keeps every server-
 * authoritative value flowing through one place.
 *
 * State lives in `useReducer` with the pure reducer from `lib/lesson/session.ts`
 * — local to this route, because a lesson session is genuinely ephemeral and
 * nothing outside this subtree needs it. No store, no context, no provider.
 */

import { useCallback, useEffect, useReducer, useRef } from "react";
import { useRouter } from "next/navigation";

import { ApiError } from "@/lib/api/client";
import {
  completeLesson,
  startLesson,
  submitAnswer,
  submitPair,
} from "@/lib/api/lessons";
import { DEFAULT_INSTRUCTIONS, narrowExercise } from "@/lib/lesson/exercise";
import type { DraftAnswer } from "@/lib/lesson/exercise";
import {
  canSubmit,
  currentExercise,
  initialState,
  isLastExercise,
  reduce,
} from "@/lib/lesson/session";

import { AnswerFeedback } from "./AnswerFeedback";
import { DuoMascot } from "./DuoMascot";
import { ExerciseRenderer } from "./ExerciseRenderer";
import { LessonComplete } from "./LessonComplete";
import { LessonHeader } from "./LessonHeader";

const PATH_ROUTE = "/learn";

function messageFor(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  return fallback;
}

export function LessonPlayer({ lessonId }: { lessonId: number }) {
  const router = useRouter();
  const [state, dispatch] = useReducer(reduce, initialState);

  /**
   * Guards against starting the lesson more than once.
   *
   * React Strict Mode intentionally runs effects twice in development, and a
   * naive `useEffect` would therefore create two attempts — two rows, and a
   * confusing history. A ref survives that double invocation (unlike state,
   * which is reset) and is checked *synchronously* before the request is issued,
   * so the second run returns before reaching the network.
   *
   * Keyed by lesson id so navigating to a different lesson does start a new
   * session.
   */
  const startedFor = useRef<number | null>(null);

  useEffect(() => {
    if (startedFor.current === lessonId) return;
    startedFor.current = lessonId;

    // Deliberately no `cancelled` flag here. The usual "ignore the result if the
    // effect was cleaned up" pattern is *wrong* when combined with a ref guard:
    // Strict Mode runs effect -> cleanup -> effect, so the cleanup would mark
    // the first request cancelled while the second run returns early at the
    // guard — and the lesson would hang on "Loading" forever. The ref already
    // guarantees exactly one request per lesson, and setting state after
    // unmount is a no-op in React 18+.
    //
    // `/start` returns the lesson as well as the attempt, so opening a session
    // is one request rather than a GET followed by a POST.
    startLesson(lessonId)
      .then((session) => {
        dispatch({
          type: "STARTED",
          lesson: session.lesson,
          attemptId: session.attempt_id,
          hearts: session.hearts,
          maxHearts: session.max_hearts,
        });
      })
      .catch((error: unknown) => {
        const outOfHearts = error instanceof ApiError && error.status === 409;
        dispatch({
          type: "FAILED",
          error: {
            stage: "load",
            outOfHearts,
            message: outOfHearts
              ? "You're out of hearts. Come back later to keep learning."
              : messageFor(error, "This lesson could not be loaded."),
          },
        });
      });
  }, [lessonId]);

  const handleDraft = useCallback((draft: DraftAnswer) => {
    dispatch({ type: "DRAFT_CHANGED", draft });
  }, []);

  const handleSubmit = useCallback(async () => {
    // Read the guard from the reducer so the button and the handler cannot
    // disagree about whether submission is allowed.
    if (!canSubmit(state) || state.attemptId === null) return;
    const exercise = currentExercise(state);
    if (!exercise || state.draft === null) return;

    dispatch({ type: "SUBMIT_STARTED" });
    try {
      const verdict = await submitAnswer(lessonId, {
        attempt_id: state.attemptId,
        exercise_id: exercise.id,
        answer: state.draft,
      });
      dispatch({ type: "ANSWER_RECEIVED", verdict });
    } catch (error: unknown) {
      const outOfHearts = error instanceof ApiError && error.status === 409;
      dispatch({
        type: "FAILED",
        error: {
          stage: "answer",
          outOfHearts,
          message: outOfHearts
            ? "You're out of hearts."
            : messageFor(error, "That answer could not be submitted."),
        },
      });
    }
  }, [lessonId, state]);

  /**
   * Grade one match-pairs selection.
   *
   * Given to `MatchPairsExercise`, which calls it on every pair the learner
   * forms. Two things happen with the result and both come from the server:
   *
   * * hearts are updated on **every** verdict, because a wrong pair costs one
   *   without the exercise being answered;
   * * when the server says the exercise is finished, its verdict is turned into
   *   the same `AnswerFeedback` bar every other exercise shows — using the
   *   fields the response carries, not values computed here.
   *
   * Errors are rethrown so the exercise can release the selection, *and* shown
   * in the player's banner. The learner needs both: their tiles back, and a
   * reason.
   */
  const handlePair = useCallback(
    async (leftId: string, rightId: string) => {
      const exercise = currentExercise(state);
      if (!exercise || state.attemptId === null) {
        throw new Error("No exercise in progress.");
      }

      try {
        const result = await submitPair(lessonId, {
          attempt_id: state.attemptId,
          exercise_id: exercise.id,
          left_id: leftId,
          right_id: rightId,
        });

        dispatch({ type: "HEARTS_UPDATED", hearts: result.hearts_remaining });

        if (result.exercise_complete) {
          dispatch({
            type: "ANSWER_RECEIVED",
            verdict: {
              correct: result.exercise_correct,
              // No expected answer to reveal: the learner has just matched every
              // pair, so there is nothing left to tell them.
              correct_answer: null,
              xp_earned: result.xp_earned,
              hearts_remaining: result.hearts_remaining,
              already_answered: result.already_answered,
              answered_count: result.answered_count,
              total_exercises: result.total_exercises,
            },
          });
        }

        return result;
      } catch (error: unknown) {
        const outOfHearts = error instanceof ApiError && error.status === 409;
        dispatch({
          type: "FAILED",
          error: {
            stage: "answer",
            outOfHearts,
            message: outOfHearts
              ? "You're out of hearts."
              : messageFor(error, "That pair could not be checked."),
          },
        });
        throw error;
      }
    },
    [lessonId, state],
  );

  const handleComplete = useCallback(async () => {
    if (state.attemptId === null) return;
    dispatch({ type: "COMPLETE_STARTED" });
    try {
      const completion = await completeLesson(lessonId, {
        attempt_id: state.attemptId,
      });
      dispatch({ type: "COMPLETED", completion });
    } catch (error: unknown) {
      dispatch({
        type: "FAILED",
        error: {
          stage: "complete",
          outOfHearts: false,
          message: messageFor(error, "The lesson could not be completed."),
        },
      });
    }
  }, [lessonId, state.attemptId]);

  const handleContinue = useCallback(() => {
    // The backend decides whether completion is valid; reaching the last
    // exercise only means it is time to *ask*.
    if (isLastExercise(state)) {
      void handleComplete();
    } else {
      dispatch({ type: "CONTINUE" });
    }
  }, [state, handleComplete]);

  const exit = useCallback(() => {
    // Abandoned attempts are allowed; leaving simply navigates away. Nothing is
    // completed, and no cleanup call is made.
    //
    // `refresh()` after the push is what makes the learning path show the XP,
    // hearts, streak and crowns this lesson just changed. `/learn` is a Server
    // Component, so without it the client router could serve the cached RSC
    // payload it already had and the path would look stale. This is the whole
    // "stats refresh" mechanism -- no store, no global state (ADR-44).
    router.push(PATH_ROUTE);
    router.refresh();
  }, [router]);

  // ---------------------------------------------------------------- loading
  if (state.status === "loading") {
    return (
      // `role="status"` so a screen-reader user is told the wait is deliberate:
      // without it the page is silent until the lesson appears, which is
      // indistinguishable from nothing having happened.
      <div
        role="status"
        className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4"
      >
        <div className="h-16 w-16 animate-pulse rounded-full bg-green/20" aria-hidden="true" />
        <p className="text-body-md text-text-secondary">Loading your lesson…</p>
      </div>
    );
  }

  // ------------------------------------------------------- blocking failures
  if (state.status === "failed" && state.error) {
    const { outOfHearts, message } = state.error;
    return (
      <div className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-5 px-4 text-center">
        <div
          className={`flex h-20 w-20 items-center justify-center rounded-full ${
            outOfHearts ? "bg-red/10" : "bg-border/60"
          }`}
        >
          <span className="text-4xl" aria-hidden="true">
            {outOfHearts ? "💔" : "⚠️"}
          </span>
        </div>
        <h1 className="text-headline-lg text-text">
          {outOfHearts ? "Out of hearts" : "Something went wrong"}
        </h1>
        <p className="text-body-md text-text-secondary">{message}</p>
        <button type="button" onClick={exit} className="tactile btn-primary w-full">
          Back to learning path
        </button>
      </div>
    );
  }

  // ------------------------------------------------------------- completion
  if (state.status === "completed" && state.completion) {
    return (
      <div className="flex min-h-dvh flex-col">
        <LessonComplete result={state.completion} onDone={exit} />
      </div>
    );
  }

  if (!state.lesson) return null;

  const exercise = currentExercise(state);
  const narrowed = exercise ? narrowExercise(exercise) : null;
  const total = state.lesson.exercises.length;
  const answered = state.submission === "answered";

  return (
    <div className="flex min-h-dvh flex-col">
      <LessonHeader
        completed={state.index + (answered ? 1 : 0)}
        total={total}
        hearts={state.hearts}
        maxHearts={state.maxHearts}
        onExit={exit}
      />

      {/* Bottom padding leaves room for the fixed feedback bar. */}
      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-7 px-4 pb-56 pt-2 sm:pt-6">
        {exercise && (
          <div className="flex flex-col gap-1">
            <span className="text-label-md uppercase text-text-secondary">
              {exercise.instruction || DEFAULT_INSTRUCTIONS[exercise.type]}
            </span>
            {/* A translate exercise shows its prompt in the mascot's speech
                bubble below, so repeating it here printed the sentence twice on
                screen and read it twice to a screen reader. The bubble carries
                the heading in that case. */}
            {exercise.type !== "TRANSLATE" && (
              <h1 className="text-headline-xl text-text">{exercise.prompt}</h1>
            )}
          </div>
        )}

        {exercise?.type === "TRANSLATE" && (
          <div className="flex items-start gap-3">
            <DuoMascot className="h-16 w-16 shrink-0 sm:h-20 sm:w-20" />
            <div className="relative rounded-2xl border-2 border-border bg-surface px-4 py-3">
              <span className="absolute -left-1.5 top-6 h-3 w-3 rotate-45 border-b-2 border-l-2 border-border bg-surface" />
              <h1 className="text-headline-md text-text">{exercise.prompt}</h1>
            </div>
          </div>
        )}

        {narrowed ? (
          <ExerciseRenderer
            // Remounts on every exercise, so each renderer's local input state
            // starts clean without any reset effect.
            key={narrowed.base.id}
            exercise={narrowed}
            disabled={state.submission !== "ready"}
            verdict={state.verdict}
            onDraftChange={handleDraft}
            onSubmit={() => void handleSubmit()}
            onSubmitPair={handlePair}
          />
        ) : (
          <p className="rounded-2xl border-2 border-red/40 bg-red/5 p-4 text-body-md text-red-depth">
            This exercise could not be displayed. You can skip it by leaving the
            lesson.
          </p>
        )}

        {/* A non-blocking error banner for retryable failures, so the lesson
            stays on screen rather than being replaced by an error page. */}
        {state.error && state.error.stage !== "load" && (
          <div
            role="alert"
            className="flex items-center justify-between gap-3 rounded-2xl border-2 border-red/40 bg-red/5 px-4 py-3"
          >
            <span className="text-body-sm text-red-depth">
              {state.error.message}
            </span>
            <button
              type="button"
              onClick={() => dispatch({ type: "ERROR_DISMISSED" })}
              className="text-label-md uppercase text-red-depth underline"
            >
              Dismiss
            </button>
          </div>
        )}
      </main>

      {/* Check button, shown until the answer is graded.
          Match pairs is excluded: it is graded a pair at a time, so there is
          nothing to check — pressing a button after the last pair would be a
          step that does nothing. */}
      {!answered && exercise?.type !== "MATCH_PAIRS" && (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t-2 border-border bg-surface">
          <div className="mx-auto w-full max-w-2xl px-4 py-4">
            <button
              type="button"
              onClick={() => void handleSubmit()}
              disabled={!canSubmit(state)}
              className="tactile btn-primary w-full disabled:cursor-not-allowed disabled:bg-border disabled:text-text-disabled"
              style={
                canSubmit(state)
                  ? undefined
                  : {
                      borderColor: "var(--color-border)",
                      borderBottomColor: "var(--color-border-depth)",
                    }
              }
            >
              {state.submission === "submitting" ? "Checking…" : "Check"}
            </button>
          </div>
        </div>
      )}

      {answered && state.verdict && (
        <AnswerFeedback
          verdict={state.verdict}
          isLast={isLastExercise(state)}
          busy={state.status === "completing"}
          onContinue={handleContinue}
        />
      )}
    </div>
  );
}
