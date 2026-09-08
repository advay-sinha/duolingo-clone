"use client";

/**
 * "How much Spanish do you know?" — the five self-report cards.
 *
 * A Client Component because it holds a selection and makes a request; the
 * heading, the mascot and the frame around it stay on the server.
 *
 * The value sent is the enum, never the label. The sentence on the card is copy
 * and will be rewritten; `COMMON_WORDS` has to keep meaning the same thing in
 * the database, the API, the tests and here.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";

import { selectProficiency } from "@/lib/api/onboarding";
import type { ProficiencyLevel } from "@/lib/api/types";
import { PROFICIENCY_OPTIONS } from "@/lib/onboarding/options";

import { OnboardingError } from "./OnboardingError";
import { OptionList } from "./OptionList";
import { ProficiencyBars } from "./ProficiencyBars";

export function ProficiencyPicker({
  initial,
}: {
  /** What the learner chose last time, so a refresh shows their answer. */
  initial: ProficiencyLevel | null;
}) {
  const router = useRouter();
  const [selected, setSelected] = useState<ProficiencyLevel | null>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (selected === null || busy) return;
    setBusy(true);
    setError(null);
    try {
      await selectProficiency(selected);
      // `refresh()` before navigating, so the next screen's Server Component
      // fetches the onboarding status *after* this write rather than replaying
      // the payload it cached before it.
      router.refresh();
      router.push("/onboarding/start");
    } catch {
      setError("That could not be saved. Please try again.");
      setBusy(false);
    }
  }

  return (
    <>
      <OptionList
        label="How much Spanish do you know?"
        selected={selected}
        onSelect={setSelected}
        disabled={busy}
        options={PROFICIENCY_OPTIONS.map((option) => ({
          value: option.value,
          label: option.label,
          children: (
            <>
              <ProficiencyBars
                strength={option.strength}
                active={option.value === selected}
              />
              <span className="text-body-lg text-text">{option.label}</span>
            </>
          ),
        }))}
      />

      <OnboardingError message={error} />

      {/* Rendered here rather than passed to the layout's footer slot, because
          the button's disabled state depends on this component's selection —
          hoisting it would mean lifting the state into a page that has no other
          use for it. */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t-2 border-border bg-surface">
        <div className="mx-auto w-full max-w-2xl px-4 py-4">
          <button
            type="button"
            onClick={() => void submit()}
            disabled={selected === null || busy}
            className="tactile btn-primary w-full disabled:cursor-not-allowed disabled:bg-border disabled:text-text-disabled"
            style={
              selected === null || busy
                ? {
                    borderColor: "var(--color-border)",
                    borderBottomColor: "var(--color-border-depth)",
                  }
                : undefined
            }
          >
            {busy ? "Saving…" : "Continue"}
          </button>
        </div>
      </div>
    </>
  );
}
