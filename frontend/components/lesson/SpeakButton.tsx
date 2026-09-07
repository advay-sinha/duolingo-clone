"use client";

/**
 * A speaker button that pronounces a piece of Spanish.
 *
 * `type="button"` matters: inside a lesson the surrounding markup has an
 * Enter-to-submit handler, and a default-type button would submit. Pressing this
 * never advances the exercise.
 *
 * Renders nothing when the browser cannot speak, so a learner is never offered
 * a control that silently does nothing. That check happens after mount, because
 * `speechSynthesis` does not exist during server rendering — starting as
 * "unavailable" and enabling on the client also avoids a hydration mismatch.
 */

import { useSyncExternalStore } from "react";

import { isSpeechAvailable, speak, SPANISH } from "@/lib/audio/speech";

/** Never changes after load, so the subscribe function is a no-op. */
const noopSubscribe = () => () => {};

/**
 * Whether speech is available, resolved without a hydration mismatch.
 *
 * `useSyncExternalStore` exists for exactly this: a value that differs between
 * server and client. The server snapshot is `false` (there is no
 * `speechSynthesis` in Node), the client snapshot is the real check, and React
 * reconciles the two properly. The alternative — `useState` plus an effect —
 * works but triggers a cascading render, which React's own lint rule flags.
 */
function useSpeechAvailable(): boolean {
  return useSyncExternalStore(
    noopSubscribe,
    () => isSpeechAvailable(),
    () => false,
  );
}

interface Props {
  /** The Spanish to pronounce. */
  text: string;
  lang?: string;
  /** Small for inline use beside an option; medium beside a prompt. */
  size?: "sm" | "md";
  /** Names the thing being spoken, e.g. "Hola". */
  label?: string;
}

export function SpeakButton({ text, lang = SPANISH, size = "md", label }: Props) {
  const available = useSpeechAvailable();

  if (!available) return null;

  // 40px and 44px. The small variant used to be 32px, which clears the 24px
  // WCAG minimum but is a mean target next to a 64px answer tile on a phone.
  const dimension = size === "sm" ? "h-10 w-10" : "h-11 w-11";
  const icon = size === "sm" ? 16 : 20;

  return (
    <button
      type="button"
      onClick={(event) => {
        // The button often sits inside a clickable option tile; without this a
        // tap on the speaker would also select that answer.
        event.stopPropagation();
        speak(text, lang);
      }}
      aria-label={label ? `Listen to ${label}` : "Listen"}
      className={`tactile ${dimension} shrink-0 border-blue bg-blue text-white`}
      style={{ borderBottomColor: "var(--color-blue-depth)" }}
    >
      <span className="flex h-full w-full items-center justify-center">
        <svg width={icon} height={icon} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M4 9v6h4l5 4V5L8 9H4zm12.5 3a4.5 4.5 0 0 0-2.5-4v8a4.5 4.5 0 0 0 2.5-4zM14 2v2a8 8 0 0 1 0 16v2a10 10 0 0 0 0-20z" />
        </svg>
      </span>
    </button>
  );
}
