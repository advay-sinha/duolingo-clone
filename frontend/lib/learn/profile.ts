/**
 * Presentation helpers for the leaderboard and profile screens.
 *
 * Small, but extracted for the same reason as `lib/learn/path.ts`: Node's test
 * runner cannot load `.tsx`, so anything left inside a component is untestable.
 * These are the few decisions those screens make that are worth asserting.
 *
 * **None of these compute a statistic.** Ranks, XP, unlock state and every
 * aggregate arrive from the API already decided; this file only formats and
 * groups them.
 */

import type { AchievementItem, LeaderboardEntry } from "@/lib/api/types";

/** Initials for an avatar placeholder, at most two letters. */
export function initialsOf(displayName: string): string {
  return displayName
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

/**
 * Whether the top-three medal treatment applies.
 *
 * Rank comes from the server; this only decides whether to tint it.
 */
export function isMedalRank(rank: number): boolean {
  return rank >= 1 && rank <= 3;
}

/**
 * Find the caller's own row.
 *
 * Uses the server's `is_current_user` flag rather than comparing ids in the
 * client — the backend already knows who is asking, and duplicating that
 * decision here would be a second source of truth.
 */
export function findCurrentUser(
  entries: LeaderboardEntry[],
): LeaderboardEntry | null {
  return entries.find((entry) => entry.is_current_user) ?? null;
}

/** Unlocked achievements first, each group keeping its catalogue order. */
export function sortAchievements(items: AchievementItem[]): AchievementItem[] {
  return [...items].sort((a, b) => {
    if (a.unlocked === b.unlocked) return 0;
    return a.unlocked ? -1 : 1;
  });
}

/** How many are unlocked, for a "3 of 6" style summary. */
export function unlockedCount(items: AchievementItem[]): number {
  return items.filter((item) => item.unlocked).length;
}

/**
 * A human label for the ranking period.
 *
 * Falls back to whatever the server said rather than inventing a label, so the
 * screen can never claim a period the backend does not rank by.
 */
export function periodLabel(period: string): string {
  return period === "all-time" ? "All-time XP" : period;
}
