"use client";

/**
 * Translate: build a sentence from a word bank.
 *
 * Reproduces the detail from the Stitch design that is easy to miss — a token
 * moved into the answer tray leaves a **ghost placeholder** in the bank rather
 * than disappearing. Without it the bank reflows on every tap and the words
 * jump around under the learner's finger.
 */

import { useState } from "react";

import type { ExerciseComponentProps } from "../ExerciseRenderer";

interface PlacedToken {
  /** Index into the original token array — tokens can repeat, so text is not a key. */
  source: number;
  text: string;
}

export function TranslateExercise({
  tokens,
  disabled,
  verdict,
  onDraftChange,
}: ExerciseComponentProps & { tokens: string[] }) {
  // Remounted per exercise via the `key` in LessonPlayer, so no reset effect.
  const [placed, setPlaced] = useState<PlacedToken[]>([]);

  function update(next: PlacedToken[]) {
    setPlaced(next);
    onDraftChange(
      next.length > 0 ? { tokens: next.map((token) => token.text) } : null,
    );
  }

  function place(source: number) {
    if (disabled || placed.some((token) => token.source === source)) return;
    update([...placed, { source, text: tokens[source] }]);
  }

  function remove(source: number) {
    if (disabled) return;
    update(placed.filter((token) => token.source !== source));
  }

  const used = new Set(placed.map((token) => token.source));
  const trayTone =
    verdict === null
      ? "border-border"
      : verdict.correct
        ? "border-green"
        : "border-red";

  return (
    <div className="flex flex-col gap-6">
      {/* Answer tray. `role="group"` and not a bare `aria-label`: assistive
          technology ignores a label on a generic div, so the name was simply
          being dropped before Phase 8. */}
      <div
        className={`min-h-24 rounded-2xl border-2 border-dashed ${trayTone} bg-surface-subtle p-3`}
        role="group"
        aria-label="Your answer"
      >
        <div className="flex flex-wrap gap-2.5">
          {placed.length === 0 && (
            <span className="px-2 py-2 text-body-md text-text-disabled">
              Tap the words below to build your answer
            </span>
          )}
          {placed.map((token) => (
            <button
              key={token.source}
              type="button"
              disabled={disabled}
              onClick={() => remove(token.source)}
              aria-label={`Remove ${token.text}`}
              className="tactile border-border bg-surface px-4 py-2.5 text-headline-sm text-text disabled:cursor-not-allowed"
              style={{ borderBottomColor: "var(--color-border-depth)" }}
            >
              {token.text}
            </button>
          ))}
        </div>
      </div>

      {/* Word bank */}
      <div
        className="flex flex-wrap justify-center gap-3"
        role="group"
        aria-label="Word bank"
      >
        {tokens.map((token, source) =>
          used.has(source) ? (
            // Ghost: holds the slot so the bank never reflows.
            <span
              key={source}
              aria-hidden="true"
              className="rounded-2xl border-2 border-transparent bg-border/40 px-4 py-2.5 text-headline-sm text-transparent"
            >
              {token}
            </span>
          ) : (
            <button
              key={source}
              type="button"
              disabled={disabled}
              onClick={() => place(source)}
              className="tactile border-border bg-surface px-4 py-2.5 text-headline-sm text-text hover:bg-surface-subtle disabled:cursor-not-allowed disabled:opacity-50"
              style={{ borderBottomColor: "var(--color-border-depth)" }}
            >
              {token}
            </button>
          ),
        )}
      </div>
    </div>
  );
}
