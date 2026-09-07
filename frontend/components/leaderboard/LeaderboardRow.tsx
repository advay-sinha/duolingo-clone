/**
 * One row of the standings.
 *
 * The current learner's row is highlighted from the server's `is_current_user`
 * flag — the client never compares ids. The highlight uses a border, a label
 * *and* a colour rather than colour alone, so the distinction survives for
 * colour-blind users and screen readers.
 */

import type { LeaderboardEntry } from "@/lib/api/types";

/** Medal tints for the top three; everyone else gets the neutral treatment. */
const MEDALS: Record<number, { bg: string; text: string }> = {
  1: { bg: "bg-gold", text: "text-white" },
  2: { bg: "bg-border-depth", text: "text-white" },
  3: { bg: "bg-orange", text: "text-white" },
};

export function LeaderboardRow({ entry }: { entry: LeaderboardEntry }) {
  const medal = MEDALS[entry.rank];
  const initials = entry.display_name
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <li
      className={`flex items-center gap-4 rounded-2xl border-2 px-4 py-3 ${
        entry.is_current_user
          ? "border-green bg-green/10"
          : "border-border bg-surface"
      }`}
      style={{
        borderBottomWidth: 4,
        borderBottomColor: entry.is_current_user
          ? "var(--color-green-depth)"
          : "var(--color-border-depth)",
      }}
    >
      <span
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-headline-sm tabular-nums ${
          medal ? `${medal.bg} ${medal.text}` : "bg-surface-subtle text-text-secondary"
        }`}
        aria-hidden="true"
      >
        {entry.rank}
      </span>

      <span
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-surface-subtle text-label-bold text-text-secondary"
        aria-hidden="true"
      >
        {initials}
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="truncate text-headline-sm text-text">
            {entry.display_name}
          </span>
          {/* A word, not just a colour. */}
          {entry.is_current_user && (
            <span className="rounded-full bg-green px-2 py-0.5 text-caption uppercase text-white">
              You
            </span>
          )}
        </div>
        {entry.current_streak > 0 && (
          <span className="text-caption text-text-secondary">
            {entry.current_streak} day streak
          </span>
        )}
      </div>

      <span className="shrink-0 text-headline-sm tabular-nums text-green-depth">
        {entry.xp.toLocaleString()} XP
      </span>

      {/* One sentence carrying everything the row conveys visually. */}
      <span className="sr-only">
        Rank {entry.rank}. {entry.display_name}
        {entry.is_current_user ? " (you)" : ""}. {entry.xp} XP.
      </span>
    </li>
  );
}
