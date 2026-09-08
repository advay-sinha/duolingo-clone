"use client";

/**
 * "Now let's find the best place to start!" — the two starting-point cards.
 *
 * These are **actions, not a selection**, which is why there is no radio group
 * and no Continue button: the Stitch design shows two cards and tapping one is
 * the decision. Adding a confirm step would be a click that does nothing.
 *
 * The two branches diverge here and nowhere else:
 *
 * * **Start from scratch** completes onboarding on the server and goes to
 *   `/learn`. Nothing is awarded — the first skill is already available from the
 *   rule that has governed the path since Phase 3.
 * * **Find my level** records the intent and goes to the placement test.
 *   Onboarding stays open until the test finishes, which is what lets a learner
 *   close the tab and be returned to it.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";

import { selectStartingMode } from "@/lib/api/onboarding";
import type { StartingMode } from "@/lib/api/types";
import { STARTING_POINT_OPTIONS } from "@/lib/onboarding/options";

import { OnboardingError } from "./OnboardingError";

export function StartingPointPicker() {
  const router = useRouter();
  const [busy, setBusy] = useState<StartingMode | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function choose(mode: StartingMode) {
    if (busy) return;
    setBusy(mode);
    setError(null);
    try {
      const status = await selectStartingMode(mode);
      router.refresh();
      // Navigate on what the *server* says comes next, not on the button that
      // was pressed. The two agree today; if the flow ever gains a step, this
      // does not have to be found and updated.
      router.push(status.completed ? "/learn" : "/onboarding/placement");
    } catch {
      setError("That could not be saved. Please try again.");
      setBusy(null);
    }
  }

  return (
    <>
      <div className="flex flex-col gap-3">
        {STARTING_POINT_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            disabled={busy !== null}
            // Both lines matter to the decision, and an assembled name would run
            // them together without a separator.
            aria-label={`${option.title}. ${option.description}`}
            onClick={() => void choose(option.value)}
            className="tactile flex min-h-28 w-full items-center gap-4 border-border bg-surface px-5 py-4 text-left hover:bg-surface-subtle disabled:cursor-not-allowed disabled:opacity-70"
            style={{ borderBottomColor: "var(--color-border-depth)" }}
          >
            <span aria-hidden="true" className="text-4xl">
              {option.icon}
            </span>
            <span className="flex flex-col gap-1">
              <span className="text-headline-sm text-text">{option.title}</span>
              <span className="text-body-md text-text-secondary">
                {option.description}
              </span>
            </span>
            {busy === option.value && (
              <span className="ml-auto text-body-sm text-text-secondary">
                Starting…
              </span>
            )}
          </button>
        ))}
      </div>

      <OnboardingError message={error} />
    </>
  );
}
