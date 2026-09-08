"use client";

/**
 * A vertical list of large, single-select cards.
 *
 * The proficiency screen and the course picker are the same interaction — choose
 * exactly one of several — so they are the same component, and the keyboard
 * contract is written once.
 *
 * **It reuses `lib/a11y/radioGroup`**, the pure module Phase 8 extracted when the
 * audit found the lesson's radio groups claiming a role whose behaviour they had
 * not implemented. Arrow keys move *and* select, wrapping; Home and End jump to
 * the ends; Space selects; and the whole group is one tab stop rather than one
 * per card. Getting that for free is the payoff for having made it a pure
 * function instead of a hook.
 */

import { useRef } from "react";

import { radioGroupAction, radioTabIndex } from "@/lib/a11y/radioGroup";

export interface OptionItem<T extends string> {
  value: T;
  /** The accessible name of the card. Rendered content may be richer. */
  label: string;
  children: React.ReactNode;
}

export function OptionList<T extends string>({
  label,
  options,
  selected,
  onSelect,
  disabled = false,
}: {
  /** Names the group for assistive technology, e.g. "How much Spanish do you know?". */
  label: string;
  options: OptionItem<T>[];
  selected: T | null;
  onSelect: (value: T) => void;
  disabled?: boolean;
}) {
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const selectedIndex = options.findIndex((option) => option.value === selected);

  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (disabled) return;
    const action = radioGroupAction(event.key, selectedIndex, options.length);
    // Returning early *without* preventDefault matters: swallowing every key
    // would break Tab, Enter and browser shortcuts inside the group.
    if (action === null) return;

    event.preventDefault();
    if (action.type === "select") {
      const focused = buttons.current.findIndex(
        (button) => button === document.activeElement,
      );
      if (focused >= 0) onSelect(options[focused].value);
      return;
    }
    onSelect(options[action.index].value);
    buttons.current[action.index]?.focus();
  }

  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="flex flex-col gap-3"
      onKeyDown={handleKeyDown}
    >
      {options.map((option, index) => {
        const isSelected = option.value === selected;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            ref={(node) => {
              buttons.current[index] = node;
            }}
            aria-checked={isSelected}
            aria-label={option.label}
            tabIndex={radioTabIndex(index, selectedIndex)}
            disabled={disabled}
            onClick={() => onSelect(option.value)}
            className={[
              "tactile flex min-h-20 w-full items-center gap-4 px-5 py-4 text-left",
              "disabled:cursor-not-allowed disabled:opacity-70",
              isSelected
                ? "border-blue bg-blue/10"
                : "border-border bg-surface hover:bg-surface-subtle",
            ].join(" ")}
            style={{
              borderBottomColor: isSelected
                ? "var(--color-blue-depth)"
                : "var(--color-border-depth)",
            }}
          >
            {option.children}
            {/* The check mark is the Stitch design's selected affordance. It is
                decorative here: `aria-checked` above is what actually conveys
                the state, so this must not be announced twice. */}
            <span
              aria-hidden="true"
              className={`ml-auto shrink-0 text-headline-md ${
                isSelected ? "text-blue-depth" : "text-transparent"
              }`}
            >
              ✓
            </span>
          </button>
        );
      })}
    </div>
  );
}
