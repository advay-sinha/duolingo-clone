/**
 * Tests for leaderboard and profile presentation helpers.
 *
 * The recurring theme, as everywhere else in this frontend: the client formats
 * server data and never recomputes it. Two tests below deliberately supply
 * data a correct backend would not send — an out-of-order board, a mis-flagged
 * row — to prove the UI follows the response rather than second-guessing it.
 */

import assert from "node:assert/strict";
import test from "node:test";

import type { AchievementItem, LeaderboardEntry } from "@/lib/api/types";
import {
  findCurrentUser,
  initialsOf,
  isMedalRank,
  periodLabel,
  sortAchievements,
  unlockedCount,
} from "./profile.ts";

function entry(over: Partial<LeaderboardEntry> = {}): LeaderboardEntry {
  return {
    rank: 1,
    user_id: 1,
    display_name: "Alex Mercer",
    avatar_url: "",
    xp: 100,
    current_streak: 3,
    is_current_user: false,
    ...over,
  };
}

function achievement(over: Partial<AchievementItem> = {}): AchievementItem {
  return {
    id: 1,
    key: "FIRST_LESSON",
    title: "First steps",
    description: "Complete your first lesson",
    icon: "star",
    color_key: "green",
    unlocked: false,
    unlocked_at: null,
    ...over,
  };
}

// --------------------------------------------------------------------------
// Leaderboard
// --------------------------------------------------------------------------

test("initials take the first letter of up to two names", () => {
  assert.equal(initialsOf("Alex Mercer"), "AM");
  assert.equal(initialsOf("learner"), "L");
  assert.equal(initialsOf("Ana Maria Ruiz"), "AM");
});

test("initials survive awkward spacing", () => {
  assert.equal(initialsOf("  Alex   Mercer "), "AM");
});

test("only the top three ranks get a medal", () => {
  assert.equal(isMedalRank(1), true);
  assert.equal(isMedalRank(3), true);
  assert.equal(isMedalRank(4), false);
  assert.equal(isMedalRank(0), false);
});

test("the current learner is found by the server's flag", () => {
  const rows = [
    entry({ user_id: 1, rank: 1 }),
    entry({ user_id: 2, rank: 2, is_current_user: true }),
  ];

  assert.equal(findCurrentUser(rows)?.user_id, 2);
});

test("a board with nobody flagged returns null rather than guessing", () => {
  assert.equal(findCurrentUser([entry(), entry({ user_id: 2 })]), null);
});

test("the flag is trusted even when it contradicts rank order", () => {
  // The client must not decide who "you" is by position or id.
  const rows = [entry({ user_id: 9, rank: 1, is_current_user: true }), entry({ user_id: 1, rank: 2 })];

  assert.equal(findCurrentUser(rows)?.user_id, 9);
});

test("the period label falls back to whatever the server said", () => {
  assert.equal(periodLabel("all-time"), "All-time XP");
  // An unknown period is shown verbatim rather than mislabelled.
  assert.equal(periodLabel("weekly"), "weekly");
});

// --------------------------------------------------------------------------
// Achievements
// --------------------------------------------------------------------------

test("unlocked achievements sort ahead of locked ones", () => {
  const items = [
    achievement({ id: 1, unlocked: false }),
    achievement({ id: 2, unlocked: true }),
    achievement({ id: 3, unlocked: false }),
    achievement({ id: 4, unlocked: true }),
  ];

  assert.deepEqual(
    sortAchievements(items).map((i) => i.id),
    [2, 4, 1, 3],
  );
});

test("sorting preserves catalogue order within each group", () => {
  const items = [
    achievement({ id: 1, unlocked: true }),
    achievement({ id: 2, unlocked: true }),
    achievement({ id: 3, unlocked: true }),
  ];

  assert.deepEqual(
    sortAchievements(items).map((i) => i.id),
    [1, 2, 3],
  );
});

test("sorting does not mutate the input", () => {
  const items = [achievement({ id: 1, unlocked: false }), achievement({ id: 2, unlocked: true })];
  const before = items.map((i) => i.id);

  sortAchievements(items);

  assert.deepEqual(items.map((i) => i.id), before);
});

test("the unlocked count reflects the flags, not the presence of a date", () => {
  const items = [
    achievement({ id: 1, unlocked: true, unlocked_at: "2026-03-15T10:00:00Z" }),
    achievement({ id: 2, unlocked: false }),
    achievement({ id: 3, unlocked: true, unlocked_at: "2026-03-16T10:00:00Z" }),
  ];

  assert.equal(unlockedCount(items), 2);
});

test("an empty catalogue counts zero without throwing", () => {
  assert.equal(unlockedCount([]), 0);
  assert.deepEqual(sortAchievements([]), []);
});
