/**
 * The strength meter beside each proficiency option.
 *
 * Stitch draws a small bar chart that fills as the answers get stronger. It is
 * four `<span>`s of increasing height, which is a truer rendering than an image
 * would be: it takes its colours from the theme, scales with the text, and costs
 * nothing to ship.
 *
 * `aria-hidden`, deliberately. The meter says the same thing as the label next to
 * it ("I know some common words"), and a screen reader announcing "chart, 2 of 4"
 * alongside that is noise, not information.
 */

import { PROFICIENCY_BARS } from "@/lib/onboarding/options";

export function ProficiencyBars({
  strength,
  active,
}: {
  /** How many bars are filled, 0–`PROFICIENCY_BARS`. */
  strength: number;
  /** Whether this option is the selected one, which tints the filled bars. */
  active: boolean;
}) {
  return (
    <span
      aria-hidden="true"
      className="flex h-8 w-9 shrink-0 items-end gap-0.5"
    >
      {Array.from({ length: PROFICIENCY_BARS }, (_, index) => {
        const filled = index < strength;
        return (
          <span
            key={index}
            className={`w-1.5 rounded-sm ${
              filled
                ? active
                  ? "bg-blue-depth"
                  : "bg-blue"
                : "bg-border"
            }`}
            // Heights climb 40% -> 100% across the four bars, so an unfilled
            // meter still reads as a chart rather than as four identical dots.
            style={{ height: `${40 + index * 20}%` }}
          />
        );
      })}
    </span>
  );
}
