/**
 * One achievement, locked or unlocked.
 *
 * Locked and unlocked use the same layout and differ by saturation, an explicit
 * "Locked" / "Unlocked" word, and a lock glyph — never by colour alone. A locked
 * card still shows its title and description, because knowing what there is to
 * earn is the point; what it does not show is how the condition is evaluated,
 * which stays on the server.
 */

import type { AchievementItem } from "@/lib/api/types";

/** Inline glyphs keyed by the seed's `icon` value. */
const GLYPHS: Record<string, string> = {
  star: "M12 2.5 14.9 8l6.1.9-4.4 4.3 1 6.1-5.6-3-5.6 3 1-6.1L3 8.9 9.1 8 12 2.5z",
  crown: "M5 16 3 6l5 3 4-6 4 6 5-3-2 10H5zm0 2h14v2H5v-2z",
  bolt: "M13 2 4 14h6l-1 8 9-12h-6l1-8z",
  flame:
    "M13 2c.5 3.5-1.5 5-3 6.5S7 12 7 14a5 5 0 0 0 10 0c0-2.5-1.5-4-2.5-5.5C13.4 6.9 13 4.4 13 2z",
  target:
    "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 4a6 6 0 1 1 0 12 6 6 0 0 1 0-12zm0 4a2 2 0 1 0 0 4 2 2 0 0 0 0-4z",
};

const TONES: Record<string, { bg: string; fg: string }> = {
  green: { bg: "bg-green/15", fg: "text-green-depth" },
  blue: { bg: "bg-blue/15", fg: "text-blue-depth" },
  gold: { bg: "bg-gold/20", fg: "text-gold-depth" },
  orange: { bg: "bg-orange/15", fg: "text-orange-depth" },
  purple: { bg: "bg-purple/20", fg: "text-purple-depth" },
};

export function AchievementCard({ item }: { item: AchievementItem }) {
  const tone = TONES[item.color_key] ?? TONES.gold;
  const glyph = GLYPHS[item.icon] ?? GLYPHS.star;

  const unlockedOn = item.unlocked_at
    ? new Date(item.unlocked_at).toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : null;

  return (
    <li
      className={`card flex items-start gap-4 p-4 ${item.unlocked ? "" : "opacity-60"}`}
    >
      <span
        className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl ${
          item.unlocked ? `${tone.bg} ${tone.fg}` : "bg-surface-subtle text-text-disabled"
        }`}
        aria-hidden="true"
      >
        {item.unlocked ? (
          <svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor">
            <path d={glyph} />
          </svg>
        ) : (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2a5 5 0 0 0-5 5v3H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8a2 2 0 0 0-2-2h-1V7a5 5 0 0 0-5-5zm0 2a3 3 0 0 1 3 3v3H9V7a3 3 0 0 1 3-3z" />
          </svg>
        )}
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-headline-sm text-text">{item.title}</h3>
          <span
            className={`rounded-full px-2 py-0.5 text-caption uppercase ${
              item.unlocked
                ? "bg-green/20 text-green-depth"
                : "bg-surface-subtle text-text-secondary"
            }`}
          >
            {item.unlocked ? "Unlocked" : "Locked"}
          </span>
        </div>
        <p className="mt-0.5 text-body-sm text-text-secondary">
          {item.description}
        </p>
        {unlockedOn && (
          <p className="mt-1 text-caption text-text-secondary">
            Earned {unlockedOn}
          </p>
        )}
      </div>
    </li>
  );
}
