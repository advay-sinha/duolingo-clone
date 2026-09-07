"use client";

/**
 * Multiple choice: pick one option.
 *
 * The options carry `{id, text}` and nothing else — there is no `correct` flag
 * to inspect, because the backend never sends one. After grading, the tile the
 * learner picked turns green or red purely from the server's verdict.
 */

import { useRef, useState } from "react";

import { SpeakButton } from "@/components/lesson/SpeakButton";
import { radioGroupAction, radioTabIndex } from "@/lib/a11y/radioGroup";
import type { ChoiceOption } from "@/lib/lesson/exercise";
import type { ExerciseComponentProps } from "../ExerciseRenderer";

export function MultipleChoiceExercise({
  options,
  disabled,
  verdict,
  onDraftChange,
}: ExerciseComponentProps & { options: ChoiceOption[] }) {
  // No reset effect needed: LessonPlayer gives the renderer a `key` of the
  // exercise id, so React remounts this component for each exercise and local
  // state starts fresh. That is the idiomatic alternative to resetting state
  // from an effect, and it avoids a cascading render.
  const [selected, setSelected] = useState<string | null>(null);
  // One ref per option, so an arrow key can move focus as well as selection —
  // the DOM part of the radio-group contract. The decision of *where* to move
  // lives in `lib/a11y/radioGroup`, which is pure and tested without a browser.
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);

  const selectedIndex = options.findIndex((option) => option.id === selected);

  function choose(id: string) {
    if (disabled) return;
    setSelected(id);
    onDraftChange({ option_id: id });
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (disabled) return;
    const action = radioGroupAction(event.key, selectedIndex, options.length);
    if (action === null) return;

    // Only now: an unhandled key must keep its default behaviour, or Tab and
    // Enter stop working inside the group.
    event.preventDefault();
    if (action.type === "select") {
      const focused = buttons.current.findIndex(
        (button) => button === document.activeElement,
      );
      if (focused >= 0) choose(options[focused].id);
      return;
    }
    // Arrow keys select as well as move, which is what a radio group does.
    choose(options[action.index].id);
    buttons.current[action.index]?.focus();
  }

  return (
    <div
      className="grid gap-3 sm:grid-cols-2"
      role="radiogroup"
      aria-label="Answer options"
      onKeyDown={handleKeyDown}
    >
      {options.map((option, index) => {
        const isSelected = selected === option.id;
        // Colour after grading comes from the server's verdict, never from any
        // client-side notion of which option is right.
        const graded = verdict !== null && isSelected;
        const state = graded ? (verdict.correct ? "correct" : "incorrect") : null;

        return (
          // The speaker is a sibling of the tile, never nested inside it:
          // a button within a button is invalid HTML and breaks keyboard
          // navigation.
          <div key={option.id} className="flex items-center gap-2">
            <button
              type="button"
              role="radio"
              ref={(node) => {
                buttons.current[index] = node;
              }}
              aria-checked={isSelected}
              tabIndex={radioTabIndex(index, selectedIndex)}
              disabled={disabled}
              onClick={() => choose(option.id)}
              className={[
                "tactile min-h-16 flex-1 px-5 py-4 text-left text-body-lg transition-colors",
                "disabled:cursor-not-allowed",
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
              {option.text}
            </button>
            {/* The options are the Spanish side, so each is worth hearing. */}
            <SpeakButton text={option.text} label={option.text} size="sm" />
          </div>
        );
      })}
    </div>
  );
}
