"use client";

/**
 * The placement test session controller.
 *
 * The same shape as `LessonPlayer` — one component owns the API calls, the
 * exercise renderers stay ignorant of HTTP — and it **reuses those renderers
 * directly**. Placement asks real questions from the seeded course, so building a
 * second set of multiple-choice and typing components would have been four files
 * of duplication that could drift.
 *
 * What it does *not* reuse is `LessonPlayer` itself, and that is the point of
 * separating them: the lesson player deducts hearts, tracks XP, completes an
 * attempt and refreshes the path. None of that may happen here. The shared part
 * is rendering a question; the different part is everything that follows an
 * answer.
 *
 * **The client never decides anything about placement.** It sends an answer and
 * is told: whether it was right, what to ask next, and — at the end — which
 * skill the learner starts at. There is no scoring here, no difficulty
 * arithmetic, and no level.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { ExerciseRenderer } from "@/components/lesson/ExerciseRenderer";
import { DuoMascot } from "@/components/lesson/DuoMascot";
import { ApiError } from "@/lib/api/client";
import {
  answerPlacement,
  completePlacement,
  startPlacement,
} from "@/lib/api/placement";
import type {
  PlacementAnswerResult,
  PlacementResult,
  PlacementState,
} from "@/lib/api/types";
import { DEFAULT_INSTRUCTIONS, narrowExercise } from "@/lib/lesson/exercise";
import type { DraftAnswer } from "@/lib/lesson/exercise";

import { PlacementProgress } from "./PlacementProgress";
import { PlacementResultCard } from "./PlacementResultCard";

/** Difficulty bands the backend uses. Display only — nothing is computed from it. */
const LEVELS = 5;

function messageFor(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  return fallback;
}

/**
 * Match pairs is never asked in a placement test — the backend's
 * `ELIGIBLE_TYPES` excludes it, because it is graded a pair at a time against a
 * heart budget that placement does not have. `ExerciseRenderer` requires the
 * handler anyway (so the lesson player cannot forget it), so this stands in and
 * fails loudly rather than silently doing nothing if that ever changes.
 */
function noPairsInPlacement(): Promise<never> {
  return Promise.reject(
    new Error("Match pairs is not used in the placement test."),
  );
}

export function PlacementRunner() {
  const router = useRouter();

  const [state, setState] = useState<PlacementState | null>(null);
  const [draft, setDraft] = useState<DraftAnswer>(null);
  const [verdict, setVerdict] = useState<PlacementAnswerResult | null>(null);
  const [result, setResult] = useState<PlacementResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Guards against starting twice.
   *
   * React Strict Mode runs effects twice in development. `startPlacement` is
   * idempotent server-side — it returns the open test rather than creating a
   * second — so a double call is harmless, but the ref keeps it to one request
   * and matches how `LessonPlayer` solves the same problem.
   */
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    startPlacement()
      .then(setState)
      .catch((cause: unknown) => {
        setError(messageFor(cause, "The placement test could not be started."));
      });
  }, []);

  const finish = useCallback(async (testId: number) => {
    setBusy(true);
    try {
      setResult(await completePlacement(testId));
    } catch (cause: unknown) {
      setError(messageFor(cause, "Your result could not be saved."));
    } finally {
      setBusy(false);
    }
  }, []);

  const submit = useCallback(async () => {
    if (!state?.question || draft === null || busy) return;

    setBusy(true);
    setError(null);
    try {
      setVerdict(
        await answerPlacement({
          test_id: state.test_id,
          exercise_id: state.question.exercise.id,
          answer: draft,
        }),
      );
    } catch (cause: unknown) {
      setError(messageFor(cause, "That answer could not be checked."));
    } finally {
      setBusy(false);
    }
  }, [state, draft, busy]);

  const advance = useCallback(() => {
    if (!verdict) return;
    if (verdict.finished) {
      void finish(verdict.test_id);
      return;
    }
    // The next question arrived with the verdict, so continuing costs no
    // request — and the server has already chosen its difficulty.
    setState(verdict);
    setVerdict(null);
    setDraft(null);
  }, [verdict, finish]);

  const leave = useCallback(() => {
    // Leaving mid-test is allowed and loses nothing: every answer is already
    // recorded, and returning resumes at the same question. Onboarding is still
    // incomplete, so the starting-point screen is where they belong.
    router.push("/onboarding/start");
    router.refresh();
  }, [router]);

  const goToLearn = useCallback(() => {
    router.push("/learn");
    router.refresh();
  }, [router]);

  // ---------------------------------------------------------------- result
  if (result) {
    return <PlacementResultCard result={result} onContinue={goToLearn} />;
  }

  // ------------------------------------------------------- blocking failure
  if (error && state === null) {
    return (
      <div className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-5 px-4 text-center">
        <span aria-hidden="true" className="text-5xl">
          ⚠️
        </span>
        <h1 className="text-headline-lg text-text">Something went wrong</h1>
        <p className="text-body-md text-text-secondary">{error}</p>
        <button type="button" onClick={leave} className="tactile btn-primary w-full">
          Back
        </button>
      </div>
    );
  }

  // --------------------------------------------------------------- loading
  if (state === null) {
    return (
      <div
        role="status"
        className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4"
      >
        <div
          className="h-16 w-16 animate-pulse rounded-full bg-green/20"
          aria-hidden="true"
        />
        <p className="text-body-md text-text-secondary">
          Preparing your placement test…
        </p>
      </div>
    );
  }

  const question = state.question;

  // A finished test with no result yet: the learner answered everything and
  // then reloaded. One button, and no way to be stuck.
  if (!question) {
    return (
      <div className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-5 px-4 text-center">
        <h1 className="text-headline-lg text-text">That&rsquo;s every question!</h1>
        <p className="text-body-md text-text-secondary">
          Let&rsquo;s work out where you should start.
        </p>
        <button
          type="button"
          disabled={busy}
          onClick={() => void finish(state.test_id)}
          className="tactile btn-primary w-full disabled:opacity-70"
        >
          {busy ? "Scoring…" : "See my level"}
        </button>
      </div>
    );
  }

  const narrowed = narrowExercise(question.exercise);
  const answered = verdict !== null;

  return (
    <div className="flex min-h-dvh flex-col">
      <PlacementProgress
        number={question.number}
        total={state.total_questions}
        difficulty={question.difficulty}
        levels={LEVELS}
        onExit={leave}
      />

      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-7 px-4 pb-56 pt-4">
        <div className="flex flex-col gap-1">
          <span className="text-label-md uppercase text-text-secondary">
            {question.exercise.instruction ||
              DEFAULT_INSTRUCTIONS[question.exercise.type]}
          </span>
          {question.exercise.type !== "TRANSLATE" && (
            <h1 className="text-headline-xl text-text">
              {question.exercise.prompt}
            </h1>
          )}
        </div>

        {question.exercise.type === "TRANSLATE" && (
          <div className="flex items-start gap-3">
            <DuoMascot className="h-16 w-16 shrink-0 sm:h-20 sm:w-20" />
            <div className="relative rounded-2xl border-2 border-border bg-surface px-4 py-3">
              <span
                aria-hidden="true"
                className="absolute -left-1.5 top-6 h-3 w-3 rotate-45 border-b-2 border-l-2 border-border bg-surface"
              />
              <h1 className="text-headline-md text-text">
                {question.exercise.prompt}
              </h1>
            </div>
          </div>
        )}

        {narrowed ? (
          <ExerciseRenderer
            // Remount per question, so each renderer's input state starts clean
            // with no reset effect — the same trick the lesson player uses.
            key={question.exercise.id}
            exercise={narrowed}
            disabled={answered || busy}
            verdict={verdict}
            onDraftChange={setDraft}
            onSubmit={() => void submit()}
            onSubmitPair={noPairsInPlacement}
          />
        ) : (
          <p className="rounded-2xl border-2 border-red/40 bg-red/5 p-4 text-body-md text-red-depth">
            This question could not be displayed.
          </p>
        )}

        {error && (
          <p
            role="alert"
            className="rounded-2xl border-2 border-red/40 bg-feedback-incorrect px-4 py-3 text-body-sm text-on-incorrect"
          >
            {error}
          </p>
        )}
      </main>

      <div className="fixed inset-x-0 bottom-0 z-30 border-t-2 border-border bg-surface">
        <div className="mx-auto flex w-full max-w-2xl flex-col gap-3 px-4 py-4">
          {answered && verdict && (
            // The feedback bar says right or wrong and nothing else. The
            // lesson's version reports XP here; there is none to report.
            <div
              className="animate-feedback-in flex flex-col gap-1"
              role="status"
            >
              <span
                className={`text-headline-sm ${
                  verdict.correct ? "text-on-correct" : "text-on-incorrect"
                }`}
              >
                {verdict.correct ? "Correct!" : "Not quite"}
              </span>
              {!verdict.correct && verdict.correct_answer && (
                <span className="text-body-sm text-text-secondary">
                  Answer: {verdict.correct_answer}
                </span>
              )}
            </div>
          )}

          <button
            type="button"
            onClick={() => (answered ? advance() : void submit())}
            disabled={busy || (!answered && draft === null)}
            className="tactile btn-primary w-full disabled:cursor-not-allowed disabled:bg-border disabled:text-text-disabled"
            style={
              busy || (!answered && draft === null)
                ? {
                    borderColor: "var(--color-border)",
                    borderBottomColor: "var(--color-border-depth)",
                  }
                : undefined
            }
          >
            {busy
              ? "Checking…"
              : answered
                ? verdict?.finished
                  ? "See my level"
                  : "Continue"
                : "Check"}
          </button>
        </div>
      </div>
    </div>
  );
}
