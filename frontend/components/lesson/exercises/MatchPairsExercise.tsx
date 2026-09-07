"use client";

/**
 * Match pairs: tap a Spanish word, then its meaning. The server answers at once.
 *
 * **This is the one exercise that talks to the API itself**, and the exception
 * is deliberate. Every other renderer reports a draft upward and lets
 * `LessonPlayer` submit it, because every other exercise has exactly one answer
 * and one Check press. Match pairs has *n* graded moves inside one exercise, so
 * threading each one through the player's single-draft reducer would mean
 * teaching that reducer about a shape only this exercise has.
 *
 * The boundary is kept honest by what the component is *given*: an
 * `onSubmitPair` function that returns the server's verdict. It performs no
 * grading, holds no answer, and reports hearts and completion back up so the
 * player stays the owner of session state.
 *
 * Interaction rules live in `lib/lesson/pairing.ts` as pure functions and are
 * tested without a DOM. This file renders them and manages focus.
 */

import { useCallback, useState } from "react";

import { SpeakButton } from "@/components/lesson/SpeakButton";
import type { SubmitPairResponse } from "@/lib/api/types";
import type { ChoiceOption } from "@/lib/lesson/exercise";
import {
  applyServerPairs,
  emptyPairState,
  isLocked,
  isSubmitting,
  isWrong,
  ownerOf,
  pairIndex,
  releaseSubmission,
  tapLeft,
  tapRight,
  type PairState,
} from "@/lib/lesson/pairing";
import type { ExerciseComponentProps } from "../ExerciseRenderer";

export interface MatchPairsProps extends ExerciseComponentProps {
  left: ChoiceOption[];
  right: ChoiceOption[];
  /** Ask the server to grade one pair. Resolves with its verdict. */
  onSubmitPair: (leftId: string, rightId: string) => Promise<SubmitPairResponse>;
}

export function MatchPairsExercise({
  left,
  right,
  disabled,
  onSubmitPair,
}: MatchPairsProps) {
  const [state, setState] = useState<PairState>(emptyPairState);
  // Announced to screen readers after every verdict, because a colour flash and
  // a tile going quiet are both invisible to them.
  const [announcement, setAnnouncement] = useState("");

  const grade = useCallback(
    async (next: PairState) => {
      setState(next);
      if (!next.submitting) return;

      const [leftId, rightId] = next.submitting;
      const leftText = left.find((item) => item.id === leftId)?.text ?? "";
      const rightText = right.find((item) => item.id === rightId)?.text ?? "";

      try {
        const result = await onSubmitPair(leftId, rightId);
        setState((current) => applyServerPairs(current, result));
        setAnnouncement(
          result.correct
            ? `${leftText} matches ${rightText}. ${result.matched_pairs.length} of ${left.length} matched.`
            : `${leftText} does not match ${rightText}. Try again.`,
        );
      } catch {
        // No verdict arrived, so nothing is marked wrong and no heart is
        // assumed spent. The player shows the error; this just gives the
        // selection back.
        setState(releaseSubmission);
        setAnnouncement("That pair could not be checked. Try again.");
      }
    },
    [left, right, onSubmitPair],
  );

  function tone(options: {
    locked: boolean;
    pending: boolean;
    checking: boolean;
    wrong: boolean;
  }) {
    if (options.wrong) {
      return {
        className: "border-red bg-red/10 text-on-incorrect",
        depth: "var(--color-red-depth)",
      };
    }
    if (options.locked) {
      return {
        className: "border-green bg-green/10 text-on-correct",
        depth: "var(--color-green-depth)",
      };
    }
    if (options.pending || options.checking) {
      return {
        className: `border-blue ${options.checking ? "bg-blue/20" : "bg-blue/10"} text-blue-depth`,
        depth: "var(--color-blue-depth)",
      };
    }
    return {
      className: "border-border bg-surface text-text hover:bg-surface-subtle",
      depth: "var(--color-border-depth)",
    };
  }

  const busy = state.submitting !== null || disabled;

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3 sm:gap-5">
        {/* `role="group"`: an aria-label on a plain div is ignored. */}
        <div className="flex flex-col gap-3" role="group" aria-label="Spanish words">
          {left.map((item) => {
            const locked = isLocked(state, item.id, "left");
            const checking = isSubmitting(state, item.id, "left");
            const pending = state.pending === item.id;
            const wrong = isWrong(state, item.id, "left");
            const { className, depth } = tone({ locked, pending, checking, wrong });
            const number = pairIndex(state, item.id);

            return (
              // Speaker as a sibling, not nested: a button inside a button is
              // invalid HTML and traps keyboard focus.
              <div key={item.id} className="flex items-center gap-2">
                <button
                  type="button"
                  // A locked tile is answered, so it is out of play and out of
                  // the tab order — the server has already recorded it.
                  disabled={busy || locked}
                  aria-pressed={pending || checking}
                  aria-label={
                    locked
                      ? `${item.text}, matched`
                      : wrong
                        ? `${item.text}, not a match`
                        : item.text
                  }
                  onClick={() => setState(tapLeft(state, item.id))}
                  className={`tactile relative min-h-14 flex-1 px-4 py-3 text-body-lg disabled:cursor-not-allowed ${className}`}
                  style={{ borderBottomColor: depth }}
                >
                  {item.text}
                  {number !== null && (
                    <span className="absolute -top-2 -right-2 flex h-6 w-6 items-center justify-center rounded-full bg-green text-caption text-white">
                      {number}
                    </span>
                  )}
                </button>
                {/* Left column is the Spanish side. */}
                <SpeakButton text={item.text} label={item.text} size="sm" />
              </div>
            );
          })}
        </div>

        <div
          className="flex flex-col gap-3"
          role="group"
          aria-label="English meanings"
        >
          {right.map((item) => {
            const locked = isLocked(state, item.id, "right");
            const checking = isSubmitting(state, item.id, "right");
            const wrong = isWrong(state, item.id, "right");
            const { className, depth } = tone({
              locked,
              pending: false,
              checking,
              wrong,
            });
            const owner = ownerOf(state, item.id);
            const number = owner ? pairIndex(state, owner) : null;

            return (
              <button
                key={item.id}
                type="button"
                // Also disabled while nothing is selected: a right item cannot be
                // chosen first, and a tap that silently does nothing is worse
                // than a control that says it is not available yet.
                disabled={busy || locked || state.pending === null}
                aria-pressed={checking}
                aria-label={
                  locked
                    ? `${item.text}, matched`
                    : wrong
                      ? `${item.text}, not a match`
                      : item.text
                }
                onClick={() => void grade(tapRight(state, item.id))}
                className={`tactile relative min-h-14 px-4 py-3 text-body-lg disabled:cursor-not-allowed ${className}`}
                style={{ borderBottomColor: depth }}
              >
                {item.text}
                {number !== null && (
                  <span className="absolute -top-2 -right-2 flex h-6 w-6 items-center justify-center rounded-full bg-green text-caption text-white">
                    {number}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Progress in words, so the state is not carried by colour alone. */}
      <p className="text-center text-body-sm text-text-secondary">
        {state.matched.length} of {left.length} matched
      </p>

      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>
    </div>
  );
}
