"use client";

/**
 * Type answer: free text.
 *
 * Enter submits, but only while the exercise is still unanswered — after
 * grading the same key is handled by the feedback bar's Continue button, so a
 * learner holding Enter cannot skip past the feedback without reading it.
 *
 * The client does **not** reimplement the backend's normalisation (casefolding,
 * whitespace collapsing, punctuation stripping, accent preservation). It sends
 * the raw text; the server normalises and decides. Duplicating that rule here
 * would create a second definition of "correct" that could drift.
 */

import { useState } from "react";

import type { ExerciseComponentProps } from "../ExerciseRenderer";

export function TypeAnswerExercise({
  language,
  disabled,
  verdict,
  onDraftChange,
  onSubmit,
}: ExerciseComponentProps & { language: string }) {
  // Remounted per exercise via the `key` in LessonPlayer, so state starts empty
  // and `autoFocus` below fires on each new exercise -- no reset effect needed.
  const [text, setText] = useState("");

  function change(value: string) {
    setText(value);
    onDraftChange(value.trim() ? { text: value } : null);
  }

  const graded = verdict !== null;
  const tone = !graded
    ? "border-border focus:border-blue"
    : verdict.correct
      ? "border-green bg-green/5"
      : "border-red bg-red/5";

  return (
    <label className="flex flex-col gap-2">
      <span className="text-label-md uppercase text-text-secondary">
        Your answer
      </span>
      <input
        // The only interactive element on the exercise, so focusing it is the
        // expected behaviour rather than a focus steal. Fires per exercise
        // because the renderer is remounted by key.
        autoFocus
        type="text"
        value={text}
        disabled={disabled}
        lang={language}
        autoComplete="off"
        autoCapitalize="off"
        autoCorrect="off"
        spellCheck={false}
        placeholder="Type here…"
        aria-invalid={graded ? !verdict.correct : undefined}
        onChange={(event) => change(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !disabled && text.trim()) {
            event.preventDefault();
            onSubmit();
          }
        }}
        className={`rounded-2xl border-2 ${tone} bg-surface-subtle px-4 py-4 text-body-lg text-text focus:bg-surface focus:outline-none disabled:opacity-60`}
      />
    </label>
  );
}
