/**
 * The coloured header above each unit's skills.
 *
 * Every string comes from the seeded unit row — title, description, and the
 * `color_key` the seed chose. Nothing is hardcoded, so editing the seed changes
 * the UI with no code change.
 */

import type { UnitNode } from "@/lib/api/types";

/**
 * Maps the unit's `color_key` onto design tokens.
 *
 * A lookup rather than interpolating class names, because Tailwind only emits
 * classes it can see literally in the source — `bg-${key}` would compile to
 * nothing. Unknown keys fall back to green.
 */
const THEMES = {
  green: { bg: "bg-green", depth: "var(--color-green-depth)" },
  blue: { bg: "bg-blue", depth: "var(--color-blue-depth)" },
  purple: { bg: "bg-purple", depth: "var(--color-purple-depth)" },
  orange: { bg: "bg-orange", depth: "var(--color-orange-depth)" },
  gold: { bg: "bg-gold", depth: "var(--color-gold-depth)" },
} as const;

export function UnitBanner({ unit }: { unit: UnitNode }) {
  const theme = THEMES[unit.color_key as keyof typeof THEMES] ?? THEMES.green;

  return (
    <div
      className={`flex flex-col gap-1 rounded-2xl border-2 px-5 py-4 text-white ${theme.bg}`}
      style={{ borderColor: "transparent", borderBottomWidth: 4, borderBottomColor: theme.depth }}
    >
      <span className="text-label-md uppercase opacity-90">
        Unit {unit.order_index + 1}
      </span>
      <h2 className="text-headline-lg">{unit.title}</h2>
      {unit.description && (
        <p className="text-body-sm opacity-90">{unit.description}</p>
      )}
    </div>
  );
}
