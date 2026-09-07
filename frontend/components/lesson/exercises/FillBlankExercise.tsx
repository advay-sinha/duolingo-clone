"use client";

/**
 * Fill in the blank: choose the word that completes the sentence.
 *
 * The sentence arrives with a literal `___` marker, which is split on so the
 * chosen word can be rendered inline where the gap is. When the exercise offers
 * no options the component falls back to a text input — the backend accepts the
 * same `{text}` payload either way.
 */

import { useRef, useState } from "react";

import { SpeakButton } from "@/components/lesson/SpeakButton";
import { radioGroupAction, radioTabIndex } from "@/lib/a11y/radioGroup";
import { exerciseSpeechText } from "@/lib/audio/speech";
import type { ExerciseComponentProps } from "../ExerciseRenderer";

export function FillBlankExercise({
  sentence,
  options,
  disabled,
  verdict,
  onDraftChange,
}: ExerciseComponentProps & { sentence: string; options: string[] }) {
  const [chosen, setChosen] = useState<string>("");
  // See `MultipleChoiceExercise` for why: `role="radio"` promises arrow-key
  // navigation, so the group provides it.
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);

  const selectedIndex = options.indexOf(chosen);

  function choose(value: string) {
    if (disabled) return;
    setChosen(value);
    onDraftChange(value.trim() ? { text: value } : null);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (disabled) return;
    const action = radioGroupAction(event.key, selectedIndex, options.length);
    if (action === null) return;

    event.preventDefault();
    if (action.type === "select") {
      const focused = buttons.current.findIndex(
        (button) => button === document.activeElement,
      );
      if (focused >= 0) choose(options[focused]);
      return;
    }
    choose(options[action.index]);
    buttons.current[action.index]?.focus();
  }

  const [before, after = ""] = sentence.split("___");
  const graded = verdict !== null;
  const blankTone = !graded
    ? "border-blue text-blue-depth"
    : verdict.correct
      ? "border-green text-green-depth"
      : "border-red text-red-depth";

  return (
    <div className="flex flex-col gap-7">
      <div className="flex items-start gap-3">
        {/* The sentence is Spanish, so it is worth hearing. The blank is read
            as a pause rather than three underscores. */}
        <SpeakButton
          text={exerciseSpeechText("FILL_BLANK", { sentence }) ?? sentence}
          label="the sentence"
        />
      <p className="text-headline-lg leading-relaxed text-text">
        {before}
        <span
          className={`mx-1 inline-block min-w-24 border-b-4 ${blankTone} px-2 text-center align-baseline`}
        >
          {chosen || " "}
        </span>
        {after}
      </p>
      </div>

      {options.length > 0 ? (
        <div
          className="flex flex-wrap justify-center gap-3"
          role="radiogroup"
          aria-label="Options"
          onKeyDown={handleKeyDown}
        >
          {options.map((option, index) => {
            const isSelected = chosen === option;
            const state = graded && isSelected ? (verdict.correct ? "correct" : "incorrect") : null;
            return (
              <button
                key={option}
                type="button"
                role="radio"
                ref={(node) => {
                  buttons.current[index] = node;
                }}
                aria-checked={isSelected}
                tabIndex={radioTabIndex(index, selectedIndex)}
                disabled={disabled}
                onClick={() => choose(option)}
                className={[
                  "tactile px-5 py-3 text-headline-sm disabled:cursor-not-allowed",
                  state === "correct"
                    ? "border-green bg-green/10 text-green-depth"
                    : state === "incorrect"
                      ? "border-red bg-red/10 text-red-depth"
                      : isSelected
                        ? "border-blue bg-blue/10 text-blue-depth"
                        : "border-border bg-surface text-text hover:bg-surface-subtle",
                ].join(" ")}
                style={{
                  borderBottomColor:
                    state === "correct"
                      ? "var(--color-green-depth)"
                      : state === "incorrect"
                        ? "var(--color-red-depth)"
                        : isSelected
                          ? "var(--color-blue-depth)"
                          : "var(--color-border-depth)",
                }}
              >
                {option}
              </button>
            );
          })}
        </div>
      ) : (
        <label className="flex flex-col gap-2">
          <span className="text-label-md uppercase text-text-secondary">
            Your answer
          </span>
          <input
            type="text"
            value={chosen}
            disabled={disabled}
            autoComplete="off"
            onChange={(event) => choose(event.target.value)}
            className="rounded-2xl border-2 border-border bg-surface-subtle px-4 py-3 text-body-lg text-text focus:border-blue focus:bg-surface focus:outline-none disabled:opacity-60"
          />
        </label>
      )}
    </div>
  );
}
