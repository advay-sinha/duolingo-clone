"use client";

/**
 * The bottom feedback bar — the signature Duolingo moment.
 *
 * Everything it shows comes from the server's verdict: whether the answer was
 * correct, what the expected answer was, and how many hearts are left. Nothing
 * here is computed.
 *
 * Fixed to the bottom on every viewport (a bottom sheet on mobile, an integrated
 * band on desktop), which keeps Continue under the thumb on a phone and in a
 * predictable place on a laptop. `role="status"` announces the result to screen
 * readers when it appears.
 *
 * Text here uses the `on-correct` / `on-incorrect` tokens rather than the
 * `*-depth` brand colours: on the pale feedback grounds those measured 2.9:1 and
 * 3.5:1, which is not readable for the caption-sized chips. The tokens keep the
 * same green/red meaning at a contrast that passes — see `globals.css`.
 */

import type { SubmitAnswerResponse } from "@/lib/api/types";

interface Props {
  verdict: SubmitAnswerResponse;
  isLast: boolean;
  busy: boolean;
  onContinue: () => void;
}

export function AnswerFeedback({ verdict, isLast, busy, onContinue }: Props) {
  const correct = verdict.correct;

  return (
    <div
      role="status"
      aria-live="polite"
      className={`animate-feedback-in fixed inset-x-0 bottom-0 z-40 border-t-2 ${
        correct
          ? "border-green/30 bg-feedback-correct"
          : "border-red/30 bg-feedback-incorrect"
      }`}
    >
      <div className="mx-auto flex max-w-2xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:py-5">
        <div className="flex items-center gap-3">
          <div
            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-surface ${
              correct ? "text-green" : "text-red"
            }`}
            aria-hidden="true"
          >
            {correct ? (
              <svg width="26" height="26" viewBox="0 0 24 24">
                <path
                  d="M5 13l4 4L19 7"
                  stroke="currentColor"
                  strokeWidth="3.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  fill="none"
                />
              </svg>
            ) : (
              <svg width="26" height="26" viewBox="0 0 24 24">
                <path
                  d="M6 6l12 12M18 6L6 18"
                  stroke="currentColor"
                  strokeWidth="3.5"
                  strokeLinecap="round"
                  fill="none"
                />
              </svg>
            )}
          </div>

          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`text-headline-lg ${correct ? "text-on-correct" : "text-on-incorrect"}`}
              >
                {correct ? "Nicely done!" : "Not quite"}
              </span>
              {verdict.xp_earned > 0 && (
                <span className="rounded-full bg-green/20 px-2 py-0.5 text-caption text-on-correct">
                  +{verdict.xp_earned} XP
                </span>
              )}
              {verdict.already_answered && (
                <span className="rounded-full bg-surface/70 px-2 py-0.5 text-caption text-text-secondary">
                  Already answered
                </span>
              )}
            </div>

            {/* The backend sends the expected answer only after a wrong
                submission -- it is never available before grading. */}
            {!correct && verdict.correct_answer && (
              <p className="mt-0.5 text-body-md text-on-incorrect">
                Correct answer:{" "}
                <strong className="font-bold">{verdict.correct_answer}</strong>
              </p>
            )}
          </div>
        </div>

        <button
          type="button"
          onClick={onContinue}
          disabled={busy}
          autoFocus
          className={`tactile w-full px-8 py-3.5 text-label-lg uppercase text-white sm:w-auto ${
            correct ? "bg-green" : "bg-red"
          } disabled:opacity-70`}
          style={{
            borderColor: correct ? "var(--color-green)" : "var(--color-red)",
            borderBottomColor: correct
              ? "var(--color-green-depth)"
              : "var(--color-red-depth)",
          }}
        >
          {busy ? "Saving…" : isLast ? "Finish" : "Continue"}
        </button>
      </div>
    </div>
  );
}
