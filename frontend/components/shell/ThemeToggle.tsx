"use client";

/**
 * A three-way theme control: Light, Dark, System.
 *
 * Writes a `data-theme` attribute on `<html>` and a string to `localStorage`.
 * It deliberately holds no React state that anything else reads — the theme is
 * consumed by CSS variables, so changing it needs no re-render beyond this
 * component's own selected-button styling.
 *
 * Rendered as a `radiogroup` rather than a switch because there are three
 * choices, and "System" is not the opposite of anything.
 */

import { useSyncExternalStore } from "react";

import {
  attributeFor,
  isThemeChoice,
  THEME_STORAGE_KEY,
  type ThemeChoice,
} from "@/lib/theme";

const CHOICES: { value: ThemeChoice; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];

/** Notify listeners in this tab; `storage` only fires in *other* tabs. */
const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

function readStored(): ThemeChoice {
  try {
    const value = localStorage.getItem(THEME_STORAGE_KEY);
    return isThemeChoice(value) ? value : "system";
  } catch {
    return "system";
  }
}

export function ThemeToggle() {
  // The server cannot know the stored choice, so its snapshot is "system".
  // `useSyncExternalStore` reconciles that with the real client value without a
  // hydration mismatch — the same pattern as SpeakButton.
  const choice = useSyncExternalStore(subscribe, readStored, () => "system" as ThemeChoice);

  function select(next: ThemeChoice) {
    const attribute = attributeFor(next);
    if (attribute) {
      document.documentElement.setAttribute("data-theme", attribute);
    } else {
      // Removing it hands control back to prefers-color-scheme.
      document.documentElement.removeAttribute("data-theme");
    }

    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // Private mode: the theme still applies for this session.
    }
    listeners.forEach((listener) => listener());
  }

  return (
    <div className="card p-4">
      <h2 className="text-label-md uppercase text-text-secondary">Appearance</h2>
      <div
        role="radiogroup"
        aria-label="Colour theme"
        className="mt-3 flex gap-2"
      >
        {CHOICES.map((option) => {
          const selected = choice === option.value;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => select(option.value)}
              className={`tactile flex-1 px-3 py-2 text-label-md uppercase ${
                selected
                  ? "border-blue bg-blue/10 text-blue-depth"
                  : "border-border bg-surface text-text-secondary hover:bg-surface-subtle"
              }`}
              style={{
                borderBottomColor: selected
                  ? "var(--color-blue-depth)"
                  : "var(--color-border-depth)",
              }}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
